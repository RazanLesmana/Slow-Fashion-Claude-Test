from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from listing.models import Product

# (seller, nama, brand, kategori, size, kondisi, harga, status)
PRODUCTS = [
    ("seller1", "Linen blazer krem", "Uniqlo", "outerwear", "M", "like_new", 85000, "active"),
    ("seller1", "Trench coat beige", "Zara", "outerwear", "M", "good", 180000, "active"),
    ("seller1", "Cardigan rajut abu", "Uniqlo", "atasan", "L", "good", 70000, "sold"),
    ("seller1", "Blazer hitam", "Zara", "outerwear", "M", "like_new", 90000, "active"),
    ("seller1", "Kemeja oversized putih", "Cotton On", "atasan", "M", "like_new", 55000, "active"),
    ("seller1", "Wool coat charcoal", "Mango", "outerwear", "M", "new", 220000, "sold"),
    ("seller1", "Overshirt flanel", "Cotton On", "atasan", "M", "good", 65000, "active"),
    ("seller1", "Parka olive", "H&M", "outerwear", "L", "good", 150000, "active"),
    ("seller1", "Midi dress motif bunga", "Mango", "dress", "S", "new", 150000, "active"),
    ("seller2", "Ribbed knit top hitam", "Zara", "atasan", "S", "good", 45000, "active"),
    ("seller2", "Wide leg trousers", "H&M", "bawahan", "L", "like_new", 60000, "active"),
    ("seller2", "501 jeans light wash", "Levi's", "bawahan", "30", "good", 120000, "active"),
    ("seller2", "Chuck 70 hitam", "Converse", "sepatu", "EU 39", "good", 250000, "active"),
    ("seller2", "Denim jacket washed", "Levi's", "outerwear", "M", "good", 110000, "active"),
    ("seller2", "Puffer vest hitam", "Uniqlo", "outerwear", "M", "like_new", 95000, "active"),
    ("seller2", "Bomber jacket olive", "H&M", "outerwear", "M", "good", 130000, "active"),
    ("seller2", "Windbreaker navy", "Uniqlo", "outerwear", "M", "fair", 75000, "sold"),
    ("seller2", "Suede jacket coklat", "Pull&Bear", "outerwear", "M", "like_new", 120000, "active"),
]


def description_for(name, brand, size):
    return (
        f"{name} dari {brand}, size {size}. Sudah dicuci dan dicek sebelum dikirim, "
        "tidak ada noda atau sobek. Ukuran detail bisa dilihat di size chart."
    )


class Command(BaseCommand):
    help = "Buat ±18 produk demo untuk seller1 dan seller2 (tanpa gambar). Aman dijalankan berulang."

    def handle(self, *args, **options):
        sellers = {u.username: u for u in User.objects.filter(username__in=["seller1", "seller2"])}
        missing = {"seller1", "seller2"} - set(sellers)
        if missing:
            self.stdout.write(self.style.WARNING(
                f"User {', '.join(sorted(missing))} belum ada. Jalankan `python manage.py seed_akun` dulu."
            ))
            return

        created_count = 0
        for seller, name, brand, category, size, condition, price, status in PRODUCTS:
            _, created = Product.objects.get_or_create(
                seller=sellers[seller],
                name=name,
                defaults={
                    "brand": brand,
                    "description": description_for(name, brand, size),
                    "category": category,
                    "size": size,
                    "condition": condition,
                    "price": Decimal(price),
                    "status": status,
                },
            )
            created_count += int(created)

        self.stdout.write(self.style.SUCCESS(
            f"seed_listing selesai: {created_count} produk baru, {len(PRODUCTS) - created_count} sudah ada."
        ))
