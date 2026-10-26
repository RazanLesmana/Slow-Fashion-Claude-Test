from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from listing.models import Product
from listing.views import seller_required
from .constants import SHIPPING_FEE_PER_STORE, STATUS_CHOICES
from .forms import CheckoutForm
from .models import CartItem, Order
from .services import (
    CheckoutError, build_cart, cart_count, cart_item_data, cart_summary_data, order_data,
    orders_for, place_orders, status_counts, unavailable_reason,
)

VALID_STATUSES = dict(STATUS_CHOICES)


# ---------- Keranjang ----------

@login_required
def keranjang(request):
    return render(request, "pesanan/keranjang.html", {"cart": build_cart(request.user)})


@login_required
@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product.objects.select_related("seller", "seller__profile"), pk=product_id)
    reason = unavailable_reason(product, request.user)
    if reason:
        messages_map = {
            "Barang milikmu sendiri": "Kamu tidak bisa membeli barangmu sendiri.",
            "Sudah terjual": "Barang ini sudah terjual.",
            "Toko sedang tidak aktif": "Toko ini sedang tidak aktif.",
        }
        return JsonResponse({"success": False, "message": messages_map[reason]}, status=400)

    _, created = CartItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        return JsonResponse({
            "success": False,
            "message": "Barang ini sudah ada di keranjang.",
            "cart_count": cart_count(request.user),
        }, status=400)
    return JsonResponse({
        "success": True,
        "message": "Ditambahkan ke keranjang.",
        "cart_count": cart_count(request.user),
    })


@login_required
@require_POST
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, user=request.user)
    item.delete()
    return JsonResponse({
        "success": True,
        "message": "Barang dihapus dari keranjang.",
        **cart_summary_data(build_cart(request.user)),
    })


@login_required
@require_GET
def cart_json(request):
    cart = build_cart(request.user)
    return JsonResponse({
        "success": True,
        "message": "OK",
        **cart_summary_data(cart),
        "items": [cart_item_data(item, request.user) for item in cart["available"]],
        "unavailable": [cart_item_data(item, request.user) for item in cart["unavailable"]],
    })


# ---------- Checkout ----------

@login_required
def checkout(request):
    cart = build_cart(request.user)

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)
        # Barang yang dilihat pembeli di halaman checkout; kalau kosong pakai isi keranjang sekarang.
        product_ids = request.POST.getlist("product_ids") or [item.product_id for item in cart["available"]]
        product_ids = [pk for pk in product_ids if str(pk).isdigit()]
        if not product_ids:
            messages.error(request, "Keranjangmu masih kosong.")
            return redirect("pesanan:keranjang")
        if form.is_valid():
            try:
                checkout_ref = place_orders(
                    request.user, product_ids, form.address_data(), form.cleaned_data["payment_method"],
                )
            except CheckoutError as error:
                messages.error(
                    request,
                    f"Pembayaran dibatalkan karena barang ini sudah tidak tersedia: {', '.join(error.names)}. "
                    "Cek lagi keranjangmu.",
                )
                return redirect("pesanan:keranjang")
            return redirect("pesanan:checkout_success", checkout_ref=checkout_ref)
    else:
        if not cart["available"]:
            messages.error(request, "Belum ada barang yang bisa di-checkout di keranjangmu.")
            return redirect("pesanan:keranjang")
        form = CheckoutForm(user=request.user)

    return render(request, "pesanan/checkout.html", {
        "form": form,
        "cart": cart,
        "shipping_per_store": SHIPPING_FEE_PER_STORE,
    })


@login_required
def checkout_success(request, checkout_ref):
    orders = list(
        Order.objects.filter(checkout_ref=checkout_ref, buyer=request.user)
        .select_related("seller").prefetch_related("items").order_by("pk")
    )
    if not orders:
        raise Http404("Pesanan tidak ditemukan.")
    store_names = [order.store_name for order in orders]
    return render(request, "pesanan/checkout_success.html", {
        "orders": orders,
        "store_names": " dan ".join([", ".join(store_names[:-1]), store_names[-1]]) if len(store_names) > 1 else store_names[0],
        "grand_total": sum(order.total for order in orders),
    })


# ---------- Pesanan ----------

def _order_list(request, role, template):
    orders = orders_for(request.user, role)
    counts = status_counts(orders)
    return render(request, template, {
        "role": role,
        "orders": [order_data(order, request.user) for order in orders],
        "counts": counts,
        # (value, label, jumlah) untuk tab; value kosong = Semua
        "status_tabs": [("", "Semua", counts["semua"])] + [
            (value, label, counts[value]) for value, label in STATUS_CHOICES
        ],
    })


@login_required
def pesanan_saya(request):
    return _order_list(request, "buyer", "pesanan/pesanan_saya.html")


@seller_required
def pesanan_masuk(request):
    return _order_list(request, "seller", "pesanan/pesanan_masuk.html")


def get_participant_order(request, code):
    """Pesanan yang melibatkan user (buyer/seller); selain itu 404."""
    order = get_object_or_404(
        Order.objects.select_related("buyer", "seller", "cancelled_by").prefetch_related("items__product__images"),
        code=code,
    )
    if not order.is_participant(request.user):
        raise Http404("Pesanan tidak ditemukan.")
    return order


@login_required
def order_detail(request, code):
    order = get_participant_order(request, code)
    return render(request, "pesanan/order_detail.html", {
        "order": order,
        "data": order_data(order, request.user),
        "is_buyer": order.buyer_id == request.user.pk,
    })


def _status_action(request, code, allowed, action, message, error):
    order = get_participant_order(request, code)
    if not allowed(order):
        return JsonResponse({"success": False, "message": error}, status=400)
    action(order)
    order.refresh_from_db()
    role = "seller" if order.seller_id == request.user.pk else "buyer"
    return JsonResponse({
        "success": True,
        "message": message,
        "order": order_data(order, request.user),
        "counts": status_counts(orders_for(request.user, role)),
    })


@login_required
@require_POST
def order_ship(request, code):
    return _status_action(
        request, code,
        allowed=lambda order: order.can_ship(request.user),
        action=lambda order: order.mark_shipped(),
        message="Pesanan ditandai dikirim.",
        error="Hanya seller yang bisa mengirim pesanan berstatus Diproses.",
    )


@login_required
@require_POST
def order_complete(request, code):
    return _status_action(
        request, code,
        allowed=lambda order: order.can_complete(request.user),
        action=lambda order: order.mark_completed(),
        message="Terima kasih! Pesanan selesai.",
        error="Hanya pembeli yang bisa menyelesaikan pesanan berstatus Dikirim.",
    )


@login_required
@require_POST
def order_cancel(request, code):
    return _status_action(
        request, code,
        allowed=lambda order: order.can_cancel(request.user),
        action=lambda order: order.cancel(request.user),
        message="Pesanan dibatalkan. Barangnya kembali dijual.",
        error="Pesanan hanya bisa dibatalkan selama masih Diproses.",
    )


@login_required
@require_GET
def orders_json(request):
    role = request.GET.get("role", "buyer")
    if role not in ("buyer", "seller"):
        role = "buyer"
    if role == "seller":
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.is_seller:
            return JsonResponse({"success": False, "message": "Hanya untuk seller."}, status=403)

    all_orders = orders_for(request.user, role)
    status = request.GET.get("status", "")
    orders = all_orders.filter(status=status) if status in VALID_STATUSES else all_orders
    return JsonResponse({
        "success": True,
        "message": "OK",
        "role": role,
        "status": status if status in VALID_STATUSES else "",
        "counts": status_counts(all_orders),
        "orders": [order_data(order, request.user) for order in orders],
    })
