from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from listing.models import Product
from .forms import ProfileForm
from .models import Profile

PASSWORD = "demo12345"


def make_user(username, is_seller=False, bio=""):
    user = User.objects.create_user(username=username, password=PASSWORD)
    Profile.objects.update_or_create(user=user, defaults={"is_seller": is_seller, "bio": bio})
    return user


def make_product(seller, name="Linen blazer krem", status="active"):
    return Product.objects.create(
        seller=seller, name=name, brand="Uniqlo", description="Deskripsi",
        category="outerwear", size="M", condition="good",
        price=Decimal("85000"), status=status,
    )


class ProfileModelTests(TestCase):

    def test_signal_membuat_profile_otomatis(self):
        user = User.objects.create_user(username="baru", password=PASSWORD)
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertFalse(user.profile.is_seller)

    def test_superuser_juga_punya_profile(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", PASSWORD)
        self.assertTrue(Profile.objects.filter(user=admin).exists())

    def test_str_dan_for_user_untuk_user_lama(self):
        user = make_user("lama")
        Profile.objects.filter(user=user).delete()
        profile = Profile.for_user(user)
        self.assertEqual(str(profile), "lama")
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_profile_form_adalah_modelform(self):
        user = make_user("budi")
        form = ProfileForm({"bio": "x" * 201}, instance=user.profile)
        self.assertFalse(form.is_valid())
        self.assertIn("bio", form.errors)


class RegisterLoginTests(TestCase):

    def test_register_membuat_user_dan_satu_profile(self):
        response = self.client.post(reverse("akun:register"), {
            "username": "pembeli",
            "password1": "rahasiaKuat123",
            "password2": "rahasiaKuat123",
        })
        self.assertRedirects(response, reverse("akun:profil"))
        user = User.objects.get(username="pembeli")
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_register_error_per_field(self):
        response = self.client.post(reverse("akun:register"), {
            "username": "pembeli", "password1": "abc", "password2": "xyz",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "field-error")
        self.assertFalse(User.objects.filter(username="pembeli").exists())

    def test_login_dan_logout_post(self):
        make_user("budi")
        response = self.client.post(reverse("akun:login"), {"username": "budi", "password": PASSWORD})
        self.assertRedirects(response, reverse("landing"))
        self.assertEqual(self.client.get(reverse("akun:logout")).status_code, 405)
        response = self.client.post(reverse("akun:logout"))
        self.assertRedirects(response, reverse("landing"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfilViewTests(TestCase):

    def setUp(self):
        self.user = make_user("budi", bio="Bio lama")
        self.client.login(username="budi", password=PASSWORD)

    def test_halaman_profil(self):
        response = self.client.get(reverse("akun:profil"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bio lama")
        self.assertContains(response, "Zona Bahaya")

    def test_edit_bio_via_ajax(self):
        response = self.client.post(reverse("akun:edit_profil"), {"bio": "Bio baru"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["bio"], "Bio baru")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Bio baru")

    def test_edit_bio_terlalu_panjang_ditolak(self):
        response = self.client.post(reverse("akun:edit_profil"), {"bio": "x" * 201})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertIn("bio", response.json()["errors"])

    def test_edit_bio_hanya_post(self):
        self.assertEqual(self.client.get(reverse("akun:edit_profil")).status_code, 405)

    def test_edit_bio_butuh_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="budi", password=PASSWORD)
        response = client.post(reverse("akun:edit_profil"), {"bio": "Tanpa token"})
        self.assertEqual(response.status_code, 403)

        client.get(reverse("akun:profil"))
        token = client.cookies["csrftoken"].value
        response = client.post(reverse("akun:edit_profil"), {"bio": "Dengan token"}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Dengan token")

    def test_toggle_seller_aktif_dengan_redirect_buka_toko(self):
        response = self.client.post(reverse("akun:toggle_seller"))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["is_seller"])
        self.assertEqual(data["redirect_url"], reverse("profil_toko:buka_toko"))
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.is_seller)

    def test_toggle_seller_nonaktif(self):
        Profile.objects.filter(user=self.user).update(is_seller=True)
        response = self.client.post(reverse("akun:toggle_seller"))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["is_seller"])
        self.assertNotIn("redirect_url", data)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.is_seller)

    def test_toggle_seller_hanya_post(self):
        self.assertEqual(self.client.get(reverse("akun:toggle_seller")).status_code, 405)

    def test_hapus_akun_via_ajax(self):
        response = self.client.post(reverse("akun:hapus_akun"))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["redirect_url"], reverse("landing"))
        self.assertFalse(User.objects.filter(username="budi").exists())
        self.assertFalse(Profile.objects.filter(user_id=self.user.pk).exists())

    def test_hapus_akun_hanya_post(self):
        self.assertEqual(self.client.get(reverse("akun:hapus_akun")).status_code, 405)
        self.assertTrue(User.objects.filter(username="budi").exists())

    def test_profil_json(self):
        Profile.objects.filter(user=self.user).update(is_seller=True)
        make_product(self.user)
        response = self.client.get(reverse("akun:profil_json"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["profile"]["username"], "budi")
        self.assertEqual(data["profile"]["bio"], "Bio lama")
        self.assertTrue(data["profile"]["is_seller"])
        self.assertEqual(data["profile"]["product_count"], 1)
        self.assertIn("has_store", data["profile"])


class AnonimDiblokirTests(TestCase):

    def test_halaman_dan_endpoint_butuh_login(self):
        user = make_user("budi")
        login_url = reverse("akun:login")
        for name, method in [
            ("akun:profil", "get"),
            ("akun:profil_json", "get"),
            ("akun:edit_profil", "post"),
            ("akun:toggle_seller", "post"),
            ("akun:hapus_akun", "post"),
        ]:
            response = getattr(self.client, method)(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertTrue(response.url.startswith(login_url), name)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())


class LandingTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)

    def test_landing_hanya_produk_aktif_dari_seller_aktif(self):
        mantan = make_user("mantan", is_seller=False)
        make_product(self.seller, name="Produk Aktif")
        make_product(self.seller, name="Produk Terjual", status="sold")
        make_product(mantan, name="Produk Seller Nonaktif")

        response = self.client.get(reverse("landing"))
        self.assertContains(response, "Produk Aktif")
        self.assertNotContains(response, "Produk Terjual")
        self.assertNotContains(response, "Produk Seller Nonaktif")

    def test_landing_maksimal_8_produk_terbaru(self):
        for i in range(10):
            make_product(self.seller, name=f"Produk {i:02d}")
        response = self.client.get(reverse("landing"))
        self.assertEqual(len(response.context["products"]), 8)
        self.assertContains(response, "Produk 09")
        self.assertNotContains(response, "Produk 01")

    def test_kartu_kategori_link_ke_katalog(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, reverse("product_catalog:katalog") + "?category=outerwear")

    def test_jadi_seller_ke_buka_toko_untuk_seller_tanpa_toko(self):
        self.client.login(username="seller1", password=PASSWORD)
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.context["seller_cta_url"], reverse("profil_toko:buka_toko"))

    def test_jadi_seller_ke_profil_untuk_buyer(self):
        make_user("buyer1")
        self.client.login(username="buyer1", password=PASSWORD)
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.context["seller_cta_url"], reverse("akun:profil"))


class SeedAkunTests(TestCase):

    def test_seed_idempoten(self):
        call_command("seed_akun", stdout=StringIO())
        call_command("seed_akun", stdout=StringIO())
        self.assertEqual(User.objects.filter(username__in=["seller1", "seller2", "buyer1"]).count(), 3)
        self.assertTrue(User.objects.get(username="seller1").profile.is_seller)
        self.assertFalse(User.objects.get(username="buyer1").profile.is_seller)
        self.assertTrue(User.objects.get(username="buyer1").check_password(PASSWORD))
