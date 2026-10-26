from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from akun.models import Profile
from profil_toko.models import SizeChart, Store

STORES = {
    "seller1": {
        "name": "Rara Preloved",
        "city": "Jakarta Selatan",
        "description": "Kebanyakan blazer dan outerwear ukuran M. Semua sudah dicuci dan dicek sebelum dikirim.",
        "whatsapp_number": "081234567890",
    },
    "seller2": {
        "name": "Denim Corner",
        "city": "Bandung",
        "description": "Denim, jaket, dan sneakers preloved pilihan.",
        "whatsapp_number": "6281298765432",
    },
}

# brand: {size: (lingkar dada, panjang)}, pembuat
SIZE_CHARTS = {
    "Uniqlo": ("seller1", {"S": (96, 70), "M": (102, 72), "L": (108, 74), "XL": (114, 76)}),
    "Zara": ("seller1", {"S": (94, 68), "M": (100, 70), "L": (106, 72), "XL": (112, 74)}),
    "H&M": ("seller2", {"S": (92, 67), "M": (98, 69), "L": (104, 71), "XL": (110, 73)}),
    "Mango": ("seller2", {"S": (90, 64), "M": (96, 66), "L": (102, 68), "XL": (108, 70)}),
}


class Command(BaseCommand):
    help = "Buat toko untuk seller1/seller2 dan size chart Uniqlo, Zara, H&M, Mango. Aman dijalankan berulang."

    def handle(self, *args, **options):
        sellers = {u.username: u for u in User.objects.filter(username__in=STORES)}
        missing = set(STORES) - set(sellers)
        if missing:
            self.stdout.write(self.style.WARNING(
                f"User {', '.join(sorted(missing))} belum ada. Jalankan `python manage.py seed_akun` dulu."
            ))
            return

        for username, data in STORES.items():
            user = sellers[username]
            store, created = Store.objects.get_or_create(owner=user, defaults=data)
            Profile.objects.update_or_create(user=user, defaults={"is_seller": True})
            self.stdout.write(f"- Toko {store.name} ({username}): {'dibuat' if created else 'sudah ada'}")

        created_count = 0
        for brand, (creator, sizes) in SIZE_CHARTS.items():
            for size, (chest, length) in sizes.items():
                _, created = SizeChart.objects.get_or_create(
                    brand__iexact=brand,
                    size__iexact=size,
                    defaults={
                        "brand": brand,
                        "size": size,
                        "chest_cm": chest,
                        "length_cm": length,
                        "created_by": sellers[creator],
                    },
                )
                created_count += int(created)

        self.stdout.write(self.style.SUCCESS(f"seed_toko selesai: {created_count} baris size chart baru."))
