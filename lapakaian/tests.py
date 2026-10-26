from decimal import Decimal

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from akun.models import Profile
from listing.models import Product
from listing.templatetags.format_tags import format_rupiah
from listing.utils import product_card_data


def make_user(username, is_seller=False):
    user = User.objects.create_user(username=username, password="demo12345")
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.is_seller = is_seller
    profile.save()
    return user


def make_product(seller, **kwargs):
    data = {
        "name": "Linen blazer krem",
        "brand": "Uniqlo",
        "description": "Blazer linen.",
        "category": "outerwear",
        "size": "M",
        "condition": "like_new",
        "price": Decimal("85000"),
    }
    data.update(kwargs)
    return Product.objects.create(seller=seller, **data)


class RupiahFilterTests(TestCase):

    def test_format_ribuan_tanpa_desimal(self):
        self.assertEqual(format_rupiah(85000), "Rp85.000")
        self.assertEqual(format_rupiah(Decimal("150000.00")), "Rp150.000")
        self.assertEqual(format_rupiah(Decimal("1250000.49")), "Rp1.250.000")
        self.assertEqual(format_rupiah(0), "Rp0")

    def test_nilai_kosong_dan_invalid(self):
        self.assertEqual(format_rupiah(None), "")
        self.assertEqual(format_rupiah("abc"), "abc")


class ProductQuerySetTests(TestCase):

    def test_public_hanya_produk_aktif_dari_seller_aktif(self):
        seller = make_user("seller", is_seller=True)
        nonaktif = make_user("mantan", is_seller=False)
        aktif = make_product(seller)
        make_product(seller, name="Sold", status="sold")
        make_product(nonaktif, name="Seller nonaktif")

        self.assertEqual(list(Product.objects.public()), [aktif])


class ProductCardTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller", is_seller=True)

    def test_kartu_menampilkan_nama_harga_dan_meta(self):
        product = make_product(self.seller)
        html = render_to_string("partials/product_card.html", {"product": product})
        self.assertIn("Linen blazer krem", html)
        self.assertIn("Rp85.000", html)
        self.assertIn("Uniqlo · M · Seperti Baru", html)
        self.assertIn(reverse("listing:product_detail", args=[product.pk]), html)
        self.assertNotIn("badge-sold", html)

    def test_kartu_produk_terjual_ada_badge_sold(self):
        product = make_product(self.seller, status="sold")
        html = render_to_string("partials/product_card.html", {"product": product})
        self.assertIn("badge-sold", html)
        self.assertIn("is-sold", html)

    def test_product_card_data(self):
        product = make_product(self.seller)
        data = product_card_data(product)
        self.assertEqual(data["price"], 85000)
        self.assertEqual(data["price_display"], "Rp85.000")
        self.assertEqual(data["image_url"], "")
        self.assertEqual(data["seller"], "seller")
        self.assertEqual(data["detail_url"], reverse("listing:product_detail", args=[product.pk]))


class LayoutTests(TestCase):

    def test_base_memuat_utils_js_toast_dan_footer(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, "js/utils.js")
        self.assertContains(response, 'id="toast-container"')
        self.assertContains(response, "© 2026 LaPAKAIAN · Proyek PBP Kelompok A-6, Fasilkom UI")

    def test_navbar_pengunjung(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, reverse("akun:login"))
        self.assertContains(response, reverse("akun:register"))
        self.assertContains(response, reverse("product_catalog:katalog"))
        navbar = response.content.decode().split("</nav>")[0]
        self.assertNotIn(reverse("product_catalog:wishlist"), navbar)
        self.assertNotIn("data-seller-nav", navbar)

    def test_navbar_buyer_menu_seller_tersembunyi(self):
        make_user("buyer")
        self.client.login(username="buyer", password="demo12345")
        response = self.client.get(reverse("landing"))
        self.assertContains(response, ">Wishlist<")
        self.assertContains(response, 'data-seller-nav hidden', count=2)

    def test_navbar_seller_menu_seller_tampil(self):
        make_user("seller", is_seller=True)
        self.client.login(username="seller", password="demo12345")
        response = self.client.get(reverse("landing"))
        self.assertContains(response, "My Listings")
        self.assertContains(response, reverse("profil_toko:toko_saya"))
        self.assertNotContains(response, "data-seller-nav hidden")

    def test_halaman_404_custom(self):
        response = self.client.get("/halaman-yang-tidak-ada/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Ke Katalog", status_code=404)


class AuthPageTests(TestCase):

    def test_login_dan_register_render_field_manual(self):
        for name in ("akun:login", "akun:register"):
            response = self.client.get(reverse(name))
            self.assertContains(response, "Nama pengguna")
            self.assertContains(response, "auth-photo")

    def test_login_menghormati_next(self):
        make_user("buyer")
        response = self.client.post(
            reverse("akun:login") + "?next=/katalog/",
            {"username": "buyer", "password": "demo12345", "next": "/katalog/"},
        )
        self.assertRedirects(response, "/katalog/", fetch_redirect_response=False)

    def test_login_menolak_next_eksternal(self):
        make_user("buyer")
        response = self.client.post(
            reverse("akun:login"),
            {"username": "buyer", "password": "demo12345", "next": "https://evil.example.com/"},
        )
        self.assertRedirects(response, reverse("landing"), fetch_redirect_response=False)

    def test_login_gagal_menampilkan_error(self):
        response = self.client.post(reverse("akun:login"), {"username": "x", "password": "y"})
        self.assertContains(response, "form-errors")


class StubUrlTests(TestCase):

    def test_url_lintas_modul_bisa_di_reverse(self):
        urls = [
            reverse("profil_toko:buka_toko"),
            reverse("profil_toko:toko_saya"),
            reverse("profil_toko:detail", args=["seller1"]),
            reverse("product_catalog:katalog"),
            reverse("product_catalog:wishlist"),
        ]
        # Isi halaman dikerjakan tiap modul (mis. toko yang belum ada boleh 404),
        # jadi di sini cukup dipastikan URL ter-resolve dan tidak error server.
        make_user("buyer")
        self.client.login(username="buyer", password="demo12345")
        for url in urls:
            response = self.client.get(url, follow=True)
            self.assertLess(response.status_code, 500, url)
            self.assertNotEqual(response.status_code, 405, url)

    def test_slot_template_tersedia(self):
        seller = make_user("seller", is_seller=True)
        product = make_product(seller)
        for name in (
            "profil_toko/slots/size_chart.html",
            "product_catalog/slots/wishlist_button.html",
            "ulasan/slots/product_reviews.html",
        ):
            render_to_string(name, {"product": product})
        render_to_string("ulasan/slots/store_reviews.html", {"store_owner": seller})
