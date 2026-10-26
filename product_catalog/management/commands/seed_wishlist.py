from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from listing.models import Product
from product_catalog.models import WishlistItem

ITEMS = [
    ("Linen blazer krem", "Cocok buat ke kantor, tunggu gajian."),
    ("Trench coat beige", "Tanya seller soal panjang lengan."),
    ("Midi dress motif bunga", "Buat kondangan bulan depan."),
    ("Cardigan rajut abu", ""),
    ("Chuck 70 hitam", "Cek size EU 39 pas atau tidak."),
]


class Command(BaseCommand):
    help = "Isi wishlist buyer1 dengan beberapa produk demo. Aman dijalankan berulang."

    def handle(self, *args, **options):
        buyer = User.objects.filter(username="buyer1").first()
        if buyer is None:
            self.stdout.write(self.style.WARNING("User buyer1 belum ada. Jalankan `python manage.py seed_akun` dulu."))
            return

        products = {p.name: p for p in Product.objects.filter(name__in=[name for name, _ in ITEMS])}
        if not products:
            self.stdout.write(self.style.WARNING("Produk demo belum ada. Jalankan `python manage.py seed_listing` dulu."))
            return

        created_count = 0
        for name, note in ITEMS:
            product = products.get(name)
            if product is None:
                continue
            _, created = WishlistItem.objects.get_or_create(user=buyer, product=product, defaults={"note": note})
            created_count += int(created)

        self.stdout.write(self.style.SUCCESS(f"seed_wishlist selesai: {created_count} item baru untuk buyer1."))
