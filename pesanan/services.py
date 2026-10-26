"""Logika keranjang dan checkout, dipakai view, context processor, dan seed."""
import uuid
from collections import OrderedDict

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from listing.models import Product
from listing.templatetags.format_tags import format_rupiah
from listing.utils import first_image_url
from .constants import SHIPPING_FEE_PER_STORE, STATUS_CHOICES
from .models import CartItem, Order, OrderItem, store_name_for

MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def tanggal(value, with_time=False):
    """Format tanggal Indonesia: 26 Okt 2026 (atau 26 Okt 2026, 14.05)."""
    if not value:
        return ""
    value = timezone.localtime(value)
    text = f"{value.day} {MONTHS[value.month - 1]} {value.year}"
    return f"{text}, {value:%H.%M}" if with_time else text


# ---------- Ketersediaan barang ----------

def available_q(user, prefix="product__"):
    """Q filter barang yang bisa dibeli user: aktif, seller aktif, bukan milik sendiri."""
    return (
        Q(**{f"{prefix}status": "active", f"{prefix}seller__profile__is_seller": True})
        & ~Q(**{f"{prefix}seller": user})
    )


def unavailable_reason(product, user):
    """None kalau bisa dibeli, atau alasan singkat kalau tidak."""
    if product.seller_id == user.pk:
        return "Barang milikmu sendiri"
    if product.status != "active":
        return "Sudah terjual"
    profile = getattr(product.seller, "profile", None)
    if not profile or not profile.is_seller:
        return "Toko sedang tidak aktif"
    return None


def cart_count(user):
    if not user.is_authenticated:
        return 0
    return CartItem.objects.filter(user=user).filter(available_q(user)).count()


# ---------- Ringkasan keranjang ----------

def cart_items(user):
    return (
        CartItem.objects.filter(user=user)
        .select_related("product", "product__seller", "product__seller__profile")
        .prefetch_related("product__images")
    )


def build_cart(user):
    """
    Kelompokkan isi keranjang per toko. Barang yang tidak tersedia lagi
    dipisah ke `unavailable` dan tidak dihitung di ringkasan.
    """
    groups = OrderedDict()
    unavailable = []
    for item in cart_items(user):
        reason = unavailable_reason(item.product, user)
        if reason:
            item.reason = reason
            unavailable.append(item)
            continue
        seller = item.product.seller
        group = groups.setdefault(seller.pk, {"seller": seller, "store_name": store_name_for(seller), "items": []})
        group["items"].append(item)

    available = [item for group in groups.values() for item in group["items"]]
    subtotal = sum((item.product.price for item in available), 0)
    for group in groups.values():
        group["subtotal"] = sum(item.product.price for item in group["items"])
    store_count = len(groups)
    shipping = SHIPPING_FEE_PER_STORE * store_count
    return {
        "groups": list(groups.values()),
        "unavailable": unavailable,
        "available": available,
        "item_count": len(available),
        "store_count": store_count,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": subtotal + shipping,
    }


def cart_summary_data(cart):
    return {
        "item_count": cart["item_count"],
        "store_count": cart["store_count"],
        "subtotal": int(cart["subtotal"]),
        "subtotal_display": format_rupiah(cart["subtotal"]),
        "cart_count": cart["item_count"],
    }


def cart_item_data(item, user):
    product = item.product
    return {
        "id": item.pk,
        "product_id": product.pk,
        "name": product.name,
        "brand": product.brand,
        "size": product.size,
        "condition_display": product.get_condition_display(),
        "price": int(product.price),
        "price_display": format_rupiah(product.price),
        "image_url": first_image_url(product),
        "detail_url": reverse("listing:product_detail", args=[product.pk]),
        "store_name": store_name_for(product.seller),
        "available": unavailable_reason(product, user) is None,
        "unavailable_reason": unavailable_reason(product, user),
        "remove_url": reverse("pesanan:cart_remove", args=[item.pk]),
    }


# ---------- Checkout ----------

class CheckoutError(Exception):
    def __init__(self, names):
        self.names = names
        super().__init__(", ".join(names))


@transaction.atomic
def place_orders(user, product_ids, address, payment_method):
    """
    Buat satu Order per seller untuk produk yang dibeli dan tandai produknya sold.
    Seluruh proses dibatalkan (CheckoutError) kalau ada barang yang tidak tersedia lagi.
    Mengembalikan checkout_ref.
    """
    product_ids = {int(pk) for pk in product_ids}
    # Kunci baris produk supaya dua pembeli tidak bisa membeli barang yang sama.
    locked = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=product_ids)}
    products = list(
        Product.objects.filter(pk__in=locked).select_related("seller", "seller__profile").order_by("pk")
    )

    problems = [p.name for p in products if unavailable_reason(p, user)]
    if len(products) < len(product_ids):
        problems.append("barang yang sudah dihapus seller")
    if problems or not products:
        raise CheckoutError(problems or ["keranjang kosong"])

    by_seller = OrderedDict()
    for product in products:
        by_seller.setdefault(product.seller_id, []).append(product)

    checkout_ref = uuid.uuid4()
    now = timezone.now()
    for seller_products in by_seller.values():
        subtotal = sum(p.price for p in seller_products)
        order = Order.objects.create(
            checkout_ref=checkout_ref,
            buyer=user,
            seller=seller_products[0].seller,
            payment_method=payment_method,
            subtotal=subtotal,
            shipping_fee=SHIPPING_FEE_PER_STORE,
            paid_at=now,
            **address,
        )
        OrderItem.objects.bulk_create([
            OrderItem(order=order, product=p, product_name=p.name, brand=p.brand, size=p.size, price=p.price)
            for p in seller_products
        ])

    Product.objects.filter(pk__in=[p.pk for p in products]).update(status="sold")
    # Hanya keranjang pembeli yang dikosongkan. Di keranjang user lain, barang ini
    # otomatis pindah ke grup "Tidak tersedia lagi" (dan tersedia lagi kalau pesanan dibatalkan).
    CartItem.objects.filter(user=user, product__in=products).delete()
    return checkout_ref


# ---------- Data pesanan (JSON & render JS) ----------

STATUS_LABELS = dict(STATUS_CHOICES)


def orders_for(user, role):
    field = "seller" if role == "seller" else "buyer"
    return (
        Order.objects.filter(**{field: user})
        .select_related("buyer", "seller")
        .prefetch_related("items__product__images")
    )


def status_counts(queryset):
    counts = {value: 0 for value, _ in STATUS_CHOICES}
    for status in queryset.values_list("status", flat=True):
        counts[status] += 1
    counts["semua"] = sum(counts.values())
    return counts


def order_title(order):
    items = list(order.items.all())
    if not items:
        return "Pesanan"
    extra = len(items) - 1
    return items[0].product_name + (f" +{extra} barang" if extra else "")


def order_thumb_url(order):
    for item in order.items.all():
        if item.product_id:
            return first_image_url(item.product)
    return ""


def order_data(order, user):
    """Data satu pesanan untuk user yang terlibat (buyer/seller) di pesanan itu."""
    data = {
        "code": order.code,
        "status": order.status,
        "status_display": order.get_status_display(),
        "step_index": order.step_index,
        "title": order_title(order),
        "thumb_url": order_thumb_url(order),
        "created_at": order.created_at.isoformat(),
        "created_display": tanggal(order.created_at),
        "store_name": order.store_name,
        "seller": order.seller.username,
        "buyer": order.buyer.username,
        "payment_method": order.payment_method,
        "payment_display": order.get_payment_method_display(),
        "subtotal": int(order.subtotal),
        "shipping_fee": int(order.shipping_fee),
        "total": int(order.total),
        "total_display": format_rupiah(order.total),
        "items": [
            {
                "name": item.product_name,
                "brand": item.brand,
                "size": item.size,
                "price": int(item.price),
                "price_display": format_rupiah(item.price),
                "product_id": item.product_id,
            }
            for item in order.items.all()
        ],
        "detail_url": reverse("pesanan:order_detail", args=[order.code]),
        "actions": {
            "ship": reverse("pesanan:order_ship", args=[order.code]) if order.can_ship(user) else None,
            "complete": reverse("pesanan:order_complete", args=[order.code]) if order.can_complete(user) else None,
            "cancel": reverse("pesanan:order_cancel", args=[order.code]) if order.can_cancel(user) else None,
        },
    }
    # Alamat & no. HP hanya untuk buyer dan seller pesanan ini.
    if order.is_participant(user):
        data["shipping_address"] = {
            "recipient_name": order.recipient_name,
            "phone": order.phone,
            "address": order.address,
            "city": order.city,
            "postal_code": order.postal_code,
        }
    return data
