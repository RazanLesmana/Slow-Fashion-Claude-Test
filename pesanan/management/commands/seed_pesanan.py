from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from listing.models import Product
from pesanan.models import CartItem, Order, OrderItem
from pesanan.services import CheckoutError, place_orders

ADDRESS = {
    "recipient_name": "Buyer Satu",
    "phone": "081298765432",
    "address": "Jl. Margonda Raya No. 100, Pondok Cina, Beji",
    "city": "Depok",
    "postal_code": "16424",
}

# (seller, nama produk, status akhir, metode bayar, berapa hari lalu)
ORDERS = [
    ("seller1", ["Kemeja oversized putih", "Overshirt flanel"], "diproses", "transfer", 1),
    ("seller2", ["501 jeans light wash"], "dikirim", "ewallet", 3),
    ("seller1", ["Blazer hitam"], "selesai", "transfer", 10),
    ("seller2", ["Bomber jacket olive"], "dibatalkan", "cod", 6),
    ("seller2", ["Wide leg trousers"], "selesai", "ewallet", 14),
]

# Isi keranjang buyer1: 2 toko + 1 barang yang sudah terjual (grup "Tidak tersedia lagi").
CART = ["Linen blazer krem", "Puffer vest hitam", "Cardigan rajut abu"]


class Command(BaseCommand):
    help = "Isi keranjang dan beberapa pesanan buyer1 dengan status berbeda. Aman dijalankan berulang."

    def handle(self, *args, **options):
        users = {u.username: u for u in User.objects.filter(username__in=["buyer1", "seller1", "seller2"])}
        missing = {"buyer1", "seller1", "seller2"} - set(users)
        if missing:
            self.stdout.write(self.style.WARNING(
                f"User {', '.join(sorted(missing))} belum ada. Jalankan `python manage.py seed_akun` dulu."
            ))
            return
        if not Product.objects.exists():
            self.stdout.write(self.style.WARNING("Produk demo belum ada. Jalankan `python manage.py seed_listing` dulu."))
            return

        buyer = users["buyer1"]
        created_orders = 0
        for seller, names, status, method, days_ago in ORDERS:
            if OrderItem.objects.filter(order__buyer=buyer, product_name=names[0]).exists():
                continue
            products = list(Product.objects.filter(seller=users[seller], name__in=names))
            if len(products) != len(names):
                self.stdout.write(self.style.WARNING(f"Produk {', '.join(names)} tidak ditemukan, pesanan dilewati."))
                continue
            try:
                ref = place_orders(buyer, [p.pk for p in products], ADDRESS, method)
            except CheckoutError as error:
                self.stdout.write(self.style.WARNING(f"Pesanan {', '.join(names)} dilewati: {error}"))
                continue

            order = Order.objects.get(checkout_ref=ref)
            paid = timezone.now() - timedelta(days=days_ago)
            Order.objects.filter(pk=order.pk).update(created_at=paid, paid_at=paid)
            order.refresh_from_db()
            if status in ("dikirim", "selesai"):
                order.mark_shipped()
                Order.objects.filter(pk=order.pk).update(shipped_at=paid + timedelta(days=1))
            if status == "selesai":
                order.mark_completed()
                Order.objects.filter(pk=order.pk).update(completed_at=paid + timedelta(days=3))
            if status == "dibatalkan":
                order.cancel(buyer)
                Order.objects.filter(pk=order.pk).update(cancelled_at=paid + timedelta(hours=5))
            created_orders += 1

        created_cart = 0
        for product in Product.objects.filter(name__in=CART).exclude(seller=buyer):
            _, created = CartItem.objects.get_or_create(user=buyer, product=product)
            created_cart += int(created)

        self.stdout.write(self.style.SUCCESS(
            f"seed_pesanan selesai: {created_orders} pesanan baru, {created_cart} item keranjang baru untuk buyer1."
        ))
