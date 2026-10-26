from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from listing.models import Product
from ulasan.models import Review

PRODUCT_REVIEWS = [
    ("Linen blazer krem", 5, "Bahannya adem dan sesuai foto. Pengiriman cepat."),
    ("Cardigan rajut abu", 4, "Masih tebal dan hangat, ada sedikit serabut tapi wajar untuk preloved."),
    ("501 jeans light wash", 5, "Ukuran pas, warnanya bagus banget."),
]
STORE_REVIEWS = [
    ("seller1", 5, "Seller ramah, barang dikemas rapi dan wangi."),
    ("seller2", 4, "Respons cepat di WhatsApp, deskripsi produk jujur."),
]


class Command(BaseCommand):
    help = "Buat beberapa ulasan produk dan toko dari buyer1. Aman dijalankan berulang."

    def handle(self, *args, **options):
        buyer = User.objects.filter(username="buyer1").first()
        if buyer is None:
            self.stdout.write(self.style.WARNING("User buyer1 belum ada. Jalankan `python manage.py seed_akun` dulu."))
            return

        created_count = 0
        products = {p.name: p for p in Product.objects.filter(name__in=[n for n, _, _ in PRODUCT_REVIEWS])}
        if not products:
            self.stdout.write(self.style.WARNING("Produk demo belum ada, ulasan produk dilewati (jalankan `seed_listing`)."))
        for name, rating, comment in PRODUCT_REVIEWS:
            product = products.get(name)
            if product is None or product.seller_id == buyer.pk:
                continue
            _, created = Review.objects.get_or_create(
                author=buyer, product=product, defaults={"rating": rating, "comment": comment},
            )
            created_count += int(created)

        sellers = {u.username: u for u in User.objects.filter(username__in=[u for u, _, _ in STORE_REVIEWS])}
        for username, rating, comment in STORE_REVIEWS:
            seller = sellers.get(username)
            if seller is None:
                self.stdout.write(self.style.WARNING(f"User {username} belum ada, ulasan tokonya dilewati."))
                continue
            _, created = Review.objects.get_or_create(
                author=buyer, seller=seller, defaults={"rating": rating, "comment": comment},
            )
            created_count += int(created)

        self.stdout.write(self.style.SUCCESS(f"seed_ulasan selesai: {created_count} ulasan baru dari buyer1."))
