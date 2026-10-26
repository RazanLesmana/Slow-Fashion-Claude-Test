from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from akun.models import Profile
from listing.models import Product
from .filters import parse_price
from .models import WishlistItem

PASSWORD = "demo12345"


def make_user(username, is_seller=False):
    user = User.objects.create_user(username=username, password=PASSWORD)
    Profile.objects.update_or_create(user=user, defaults={"is_seller": is_seller})
    return user


def make_product(seller, name, **kwargs):
    data = {
        "brand": "Uniqlo", "description": "Deskripsi", "category": "outerwear",
        "size": "M", "condition": "good", "price": Decimal("100000"),
    }
    data.update(kwargs)
    return Product.objects.create(seller=seller, name=name, **data)


class CatalogTestMixin:

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        self.blazer = make_product(self.seller, "Linen blazer krem", brand="Uniqlo", size="M", condition="like_new", price=Decimal("85000"))
        self.top = make_product(self.seller, "Ribbed knit top hitam", brand="Zara", category="atasan", size="S", price=Decimal("45000"))
        self.jeans = make_product(self.seller, "501 jeans light wash", brand="Levi's", category="bawahan", size="30", condition="fair", price=Decimal("120000"))
        self.coat = make_product(self.seller, "Trench coat beige", brand="zara", size="M", price=Decimal("180000"))
        self.sold = make_product(self.seller, "Wool coat terjual", status="sold")
        mantan = make_user("mantan", is_seller=False)
        self.hidden = make_product(mantan, "Produk seller nonaktif")

    def names(self, params=None):
        response = self.client.get(reverse("product_catalog:katalog"), params or {})
        self.assertEqual(response.status_code, 200)
        return {p.name for p in response.context["products"]}


class KatalogTests(CatalogTestMixin, TestCase):

    def test_katalog_publik_hanya_produk_aktif_seller_aktif(self):
        names = self.names()
        self.assertEqual(names, {"Linen blazer krem", "Ribbed knit top hitam", "501 jeans light wash", "Trench coat beige"})
        self.assertNotIn("Wool coat terjual", names)
        self.assertNotIn("Produk seller nonaktif", names)

    def test_cari_nama_atau_brand(self):
        self.assertEqual(self.names({"q": "blazer"}), {"Linen blazer krem"})
        self.assertEqual(self.names({"q": "LEVI"}), {"501 jeans light wash"})

    def test_filter_kategori(self):
        self.assertEqual(self.names({"category": "atasan"}), {"Ribbed knit top hitam"})
        self.assertEqual(len(self.names({"category": "tidak-ada"})), 4)

    def test_filter_brand_multi_case_insensitive(self):
        self.assertEqual(self.names({"brand": ["Zara"]}), {"Ribbed knit top hitam", "Trench coat beige"})
        self.assertEqual(self.names({"brand": ["Uniqlo", "Levi's"]}), {"Linen blazer krem", "501 jeans light wash"})

    def test_filter_size_dan_kondisi(self):
        self.assertEqual(self.names({"size": ["M"]}), {"Linen blazer krem", "Trench coat beige"})
        self.assertEqual(self.names({"size": ["S", "30"]}), {"Ribbed knit top hitam", "501 jeans light wash"})
        self.assertEqual(self.names({"condition": ["like_new", "fair"]}), {"Linen blazer krem", "501 jeans light wash"})

    def test_filter_harga(self):
        self.assertEqual(self.names({"min_price": "100000"}), {"501 jeans light wash", "Trench coat beige"})
        self.assertEqual(self.names({"max_price": "85.000"}), {"Linen blazer krem", "Ribbed knit top hitam"})
        self.assertEqual(self.names({"min_price": "50000", "max_price": "130000"}), {"Linen blazer krem", "501 jeans light wash"})

    def test_input_harga_invalid_diabaikan(self):
        for params in ({"min_price": "abc"}, {"max_price": "-5"}, {"min_price": "1e999"}, {"max_price": "NaN"}):
            self.assertEqual(len(self.names(params)), 4, params)
        self.assertIsNone(parse_price("abc"))
        self.assertEqual(parse_price("85.000"), Decimal("85000"))

    def test_kombinasi_filter(self):
        params = {"category": "outerwear", "brand": ["zara"], "size": ["M"], "max_price": "200000", "q": "coat"}
        self.assertEqual(self.names(params), {"Trench coat beige"})

    def test_sort(self):
        url = reverse("product_catalog:katalog")
        prices = lambda sort: [int(p.price) for p in self.client.get(url, {"sort": sort}).context["products"]]
        self.assertEqual(prices("harga_terendah"), [45000, 85000, 120000, 180000])
        self.assertEqual(prices("harga_tertinggi"), [180000, 120000, 85000, 45000])
        newest = [p.name for p in self.client.get(url, {"sort": "terbaru"}).context["products"]]
        self.assertEqual(newest[0], "Trench coat beige")
        self.assertEqual(prices("ngawur"), prices("terbaru"))

    def test_chip_filter_aktif_dan_opsi_brand(self):
        response = self.client.get(reverse("product_catalog:katalog"), {"brand": ["Zara", "Uniqlo"], "size": ["M"]})
        labels = [chip["label"] for chip in response.context["active_chips"]]
        self.assertEqual(labels, ["Zara", "Uniqlo", "M"])
        self.assertNotIn("brand=Zara", response.context["active_chips"][0]["url"])
        self.assertIn("brand=Uniqlo", response.context["active_chips"][0]["url"])
        self.assertEqual(response.context["options"]["brands"], ["Levi's", "Uniqlo", "Zara"])
        self.assertEqual(response.context["sidebar_count"], 3)

    def test_paginasi_12_dengan_query_string(self):
        for i in range(14):
            make_product(self.seller, f"Kaos {i}", category="atasan")
        url = reverse("product_catalog:katalog")
        response = self.client.get(url, {"category": "atasan"})
        self.assertEqual(len(response.context["products"]), 12)
        self.assertEqual(response.context["page_obj"].paginator.count, 15)
        self.assertContains(response, "?category=atasan&page=2")
        response = self.client.get(url, {"category": "atasan", "page": 2})
        self.assertEqual(len(response.context["products"]), 3)

    def test_katalog_json(self):
        data = self.client.get(reverse("product_catalog:katalog_json"), {"brand": "Zara", "sort": "harga_terendah"}).json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 2)
        self.assertEqual([p["name"] for p in data["products"]], ["Ribbed knit top hitam", "Trench coat beige"])
        self.assertEqual(data["filters"]["sort"], "harga_terendah")
        for key in ("id", "price_display", "detail_url", "image_url"):
            self.assertIn(key, data["products"][0])


class WishlistTests(CatalogTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.buyer = make_user("buyer1")
        self.other = make_user("buyer2")
        self.client.login(username="buyer1", password=PASSWORD)

    def toggle(self, product, client=None):
        return (client or self.client).post(reverse("product_catalog:toggle_wishlist", args=[product.pk]))

    def test_str_dan_unique_constraint(self):
        item = WishlistItem.objects.create(user=self.buyer, product=self.blazer)
        self.assertEqual(str(item), "buyer1 → Linen blazer krem")
        with self.assertRaises(IntegrityError), transaction.atomic():
            WishlistItem.objects.create(user=self.buyer, product=self.blazer)

    def test_toggle_tambah_lalu_hapus(self):
        data = self.toggle(self.blazer).json()
        self.assertEqual((data["success"], data["in_wishlist"], data["count"]), (True, True, 1))
        self.assertTrue(WishlistItem.objects.filter(user=self.buyer, product=self.blazer).exists())
        data = self.toggle(self.blazer).json()
        self.assertEqual((data["in_wishlist"], data["count"]), (False, 0))
        self.assertFalse(WishlistItem.objects.exists())

    def test_toggle_post_only_404_dan_csrf(self):
        url = reverse("product_catalog:toggle_wishlist", args=[self.blazer.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(reverse("product_catalog:toggle_wishlist", args=[999])).status_code, 404)
        client = Client(enforce_csrf_checks=True)
        client.login(username="buyer1", password=PASSWORD)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertFalse(WishlistItem.objects.exists())

    def test_halaman_wishlist_hanya_milik_sendiri(self):
        WishlistItem.objects.create(user=self.buyer, product=self.blazer, note="Tunggu gajian")
        WishlistItem.objects.create(user=self.other, product=self.top)
        response = self.client.get(reverse("product_catalog:wishlist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Linen blazer krem")
        self.assertContains(response, "Tunggu gajian")
        self.assertNotContains(response, "Ribbed knit top hitam")
        self.assertContains(response, 'aria-pressed="true"')

    def test_filter_kategori_wishlist(self):
        WishlistItem.objects.create(user=self.buyer, product=self.blazer)
        WishlistItem.objects.create(user=self.buyer, product=self.top)
        response = self.client.get(reverse("product_catalog:wishlist"), {"category": "atasan"})
        self.assertEqual([i.product.name for i in response.context["items"]], ["Ribbed knit top hitam"])
        self.assertEqual(response.context["total"], 2)

    def test_update_note_pemilik(self):
        item = WishlistItem.objects.create(user=self.buyer, product=self.blazer)
        url = reverse("product_catalog:update_note", args=[item.pk])
        data = self.client.post(url, {"note": "Buat kondangan"}).json()
        self.assertEqual((data["success"], data["note"]), (True, "Buat kondangan"))
        item.refresh_from_db()
        self.assertEqual(item.note, "Buat kondangan")
        response = self.client.post(url, {"note": "x" * 201})
        self.assertEqual(response.status_code, 400)

    def test_item_orang_lain_404(self):
        item = WishlistItem.objects.create(user=self.other, product=self.blazer, note="Asli")
        self.assertEqual(self.client.post(reverse("product_catalog:update_note", args=[item.pk]), {"note": "Hack"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("product_catalog:remove_item", args=[item.pk])).status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.note, "Asli")

    def test_remove_item(self):
        item = WishlistItem.objects.create(user=self.buyer, product=self.blazer)
        data = self.client.post(reverse("product_catalog:remove_item", args=[item.pk])).json()
        self.assertEqual((data["success"], data["count"]), (True, 0))
        self.assertFalse(WishlistItem.objects.filter(pk=item.pk).exists())

    def test_wishlist_json_hanya_milik_sendiri(self):
        WishlistItem.objects.create(user=self.buyer, product=self.blazer, note="A")
        WishlistItem.objects.create(user=self.other, product=self.top)
        data = self.client.get(reverse("product_catalog:wishlist_json")).json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["note"], "A")
        self.assertEqual(data["items"][0]["product"]["name"], "Linen blazer krem")

    def test_anonim_diarahkan_ke_login(self):
        self.client.logout()
        login_url = reverse("akun:login")
        item = WishlistItem.objects.create(user=self.buyer, product=self.blazer)
        for url, method in [
            (reverse("product_catalog:wishlist"), "get"),
            (reverse("product_catalog:wishlist_json"), "get"),
            (reverse("product_catalog:toggle_wishlist", args=[self.top.pk]), "post"),
            (reverse("product_catalog:update_note", args=[item.pk]), "post"),
            (reverse("product_catalog:remove_item", args=[item.pk]), "post"),
        ]:
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response.url.startswith(login_url), url)
        self.assertEqual(WishlistItem.objects.count(), 1)


class WishlistButtonSlotTests(CatalogTestMixin, TestCase):

    def render(self, user, product):
        request = RequestFactory().get("/katalog/?q=a")
        request.user = user
        return render_to_string("product_catalog/slots/wishlist_button.html", {"product": product, "user": user}, request=request)

    def test_anonim_link_login_dengan_next(self):
        from django.contrib.auth.models import AnonymousUser
        html = self.render(AnonymousUser(), self.blazer)
        self.assertIn(reverse("akun:login") + "?next=/katalog/%3Fq%3Da", html)
        self.assertNotIn("data-wishlist-toggle", html)

    def test_state_awal_terisi_dari_server(self):
        buyer = make_user("buyer1")
        WishlistItem.objects.create(user=buyer, product=self.blazer)
        self.assertIn('aria-pressed="true"', self.render(buyer, self.blazer))
        self.assertIn('aria-pressed="false"', self.render(buyer, self.top))

    def test_kartu_katalog_memuat_aset_sekali(self):
        response = self.client.get(reverse("product_catalog:katalog"))
        self.assertContains(response, "product_catalog/product_catalog.js", count=1)
        self.assertContains(response, "product_catalog/product_catalog.css", count=1)


class SeedWishlistTests(TestCase):

    def test_seed_tanpa_prasyarat_keluar_rapi(self):
        out = StringIO()
        call_command("seed_wishlist", stdout=out)
        self.assertIn("seed_akun", out.getvalue())
        make_user("buyer1")
        out = StringIO()
        call_command("seed_wishlist", stdout=out)
        self.assertIn("seed_listing", out.getvalue())

    def test_seed_idempoten(self):
        seller = make_user("seller1", is_seller=True)
        make_user("buyer1")
        make_product(seller, "Linen blazer krem")
        make_product(seller, "Chuck 70 hitam")
        call_command("seed_wishlist", stdout=StringIO())
        call_command("seed_wishlist", stdout=StringIO())
        self.assertEqual(WishlistItem.objects.filter(user__username="buyer1").count(), 2)
