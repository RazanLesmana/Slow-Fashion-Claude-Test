from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from akun.models import Profile

PASSWORD = "demo12345"

USERS = [
    ("seller1", True, "Rara, kurator blazer dan outerwear preloved ukuran M."),
    ("seller2", True, "Jual koleksi denim dan sneakers yang masih layak pakai."),
    ("buyer1", False, "Suka berburu thrift untuk gaya kasual sehari-hari."),
]


class Command(BaseCommand):
    help = "Buat akun demo seller1, seller2 (seller) dan buyer1. Aman dijalankan berulang."

    def handle(self, *args, **options):
        for username, is_seller, bio in USERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(PASSWORD)
                user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={"is_seller": is_seller, "bio": bio},
            )
            status = "dibuat" if created else "sudah ada"
            self.stdout.write(f"- {username} ({'seller' if is_seller else 'buyer'}): {status}")

        self.stdout.write(self.style.SUCCESS(f"seed_akun selesai. Password semua akun: {PASSWORD}"))
