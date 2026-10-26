import shutil
import tempfile
from decimal import Decimal
from io import BytesIO, StringIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from akun.models import Profile
from .models import Product, ProductImage

PASSWORD = "demo12345"
MEDIA_ROOT = tempfile.mkdtemp()


def make_user(username, is_seller=False):
    user = User.objects.create_user(username=username, password=PASSWORD)
    Profile.objects.update_or_create(user=user, defaults={"is_seller": is_seller})
    return user


def make_product(seller, **kwargs):
    data = {
        "name": "Linen blazer krem",
        "brand": "Uniqlo",
        "description": "Blazer linen potongan regular.",
        "category": "outerwear",
        "size": "M",
        "condition": "like_new",
        "price": Decimal("85000"),
    }
    data.update(kwargs)
    return Product.objects.create(seller=seller, **data)


def png_file(name="foto.png"):
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def formset_data(total=5, initial=0, prefix="images"):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "5",
    }


PRODUCT_POST = {
    "name": "Trench coat beige",
    "brand": "Zara",
    "description": "Trench coat klasik.",
    "category": "outerwear",
    "size": "M",
    "condition": "good",
    "price": "180000",
}


class ProductModelTests(TestCase):

    def test_str_dan_default_status(self):
        seller = make_user("seller1", is_seller=True)
        product = make_product(seller)
        self.assertEqual(str(product), "Linen blazer krem")
        self.assertEqual(product.status, "active")

    def test_urutan_terbaru_dulu(self):
        seller = make_user("seller1", is_seller=True)
        lama = make_product(seller, name="Lama")
        baru = make_product(seller, name="Baru")
        self.assertEqual(list(Product.objects.all()), [baru, lama])

    def test_product_image_str(self):
        seller = make_user("seller1", is_seller=True)
        product = make_product(seller)
        image = ProductImage(product=product, image="product_images/x.png")
        self.assertEqual(str(image), "Image for Linen blazer krem")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ProductCrudTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        self.client.login(username="seller1", password=PASSWORD)

    def test_halaman_tambah(self):
        response = self.client.get(reverse("listing:product_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "photo-drop")
        self.assertContains(response, 'name="images-4-image"')

    def test_create_produk_dengan_foto(self):
        data = {**PRODUCT_POST, **formset_data(), "images-0-image": png_file()}
        response = self.client.post(reverse("listing:product_create"), data)
        self.assertRedirects(response, reverse("listing:my_listings"))
        product = Product.objects.get(name="Trench coat beige")
        self.assertEqual(product.seller, self.seller)
        self.assertEqual(product.status, "active")
        self.assertEqual(product.images.count(), 1)

    def test_create_harga_nol_ditolak(self):
        data = {**PRODUCT_POST, "price": "0", **formset_data()}
        response = self.client.post(reverse("listing:product_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Harga produk harus lebih besar dari 0.")
        self.assertFalse(Product.objects.exists())

    def test_edit_produk_sendiri(self):
        product = make_product(self.seller)
        data = {**PRODUCT_POST, "name": "Nama baru", **formset_data()}
        response = self.client.post(reverse("listing:product_edit", args=[product.pk]), data)
        self.assertRedirects(response, reverse("listing:product_detail", args=[product.pk]))
        product.refresh_from_db()
        self.assertEqual(product.name, "Nama baru")

    def test_hapus_produk_via_ajax(self):
        product = make_product(self.seller)
        response = self.client.post(reverse("listing:product_delete", args=[product.pk]))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["counts"]["semua"], 0)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_hapus_hanya_post(self):
        product = make_product(self.seller)
        response = self.client.get(reverse("listing:product_delete", args=[product.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_hapus_butuh_csrf(self):
        product = make_product(self.seller)
        client = Client(enforce_csrf_checks=True)
        client.login(username="seller1", password=PASSWORD)
        response = client.post(reverse("listing:product_delete", args=[product.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_mark_sold_dan_mark_active(self):
        product = make_product(self.seller)
        response = self.client.post(reverse("listing:product_mark_sold", args=[product.pk]))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "sold")
        self.assertEqual(data["counts"], {"semua": 1, "active": 0, "sold": 1})
        product.refresh_from_db()
        self.assertEqual(product.status, "sold")

        response = self.client.post(reverse("listing:product_mark_sold", args=[product.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

        response = self.client.post(reverse("listing:product_mark_active", args=[product.pk]))
        self.assertEqual(response.json()["status"], "active")
        product.refresh_from_db()
        self.assertEqual(product.status, "active")


class OwnershipTests(TestCase):

    def setUp(self):
        self.owner = make_user("seller1", is_seller=True)
        self.other = make_user("seller2", is_seller=True)
        self.product = make_product(self.owner)
        self.client.login(username="seller2", password=PASSWORD)

    def test_seller_lain_dapat_404(self):
        pk = self.product.pk
        self.assertEqual(self.client.get(reverse("listing:product_edit", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("listing:product_edit", args=[pk]), PRODUCT_POST).status_code, 404)
        for name in ("listing:product_delete", "listing:product_mark_sold", "listing:product_mark_active"):
            self.assertEqual(self.client.post(reverse(name, args=[pk])).status_code, 404, name)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Linen blazer krem")
        self.assertEqual(self.product.status, "active")

    def test_my_listings_hanya_produk_sendiri(self):
        make_product(self.other, name="Punya seller2")
        response = self.client.get(reverse("listing:my_listings"))
        self.assertContains(response, "Punya seller2")
        self.assertNotContains(response, "Linen blazer krem")


class AuthProtectionTests(TestCase):

    def test_anonim_diredirect_ke_login(self):
        seller = make_user("seller1", is_seller=True)
        product = make_product(seller)
        login_url = reverse("akun:login")
        for url, method in [
            (reverse("listing:my_listings"), "get"),
            (reverse("listing:product_create"), "get"),
            (reverse("listing:product_edit", args=[product.pk]), "get"),
            (reverse("listing:product_delete", args=[product.pk]), "post"),
            (reverse("listing:product_mark_sold", args=[product.pk]), "post"),
            (reverse("listing:my_products_json"), "get"),
        ]:
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response.url.startswith(login_url), url)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_buyer_dapat_403(self):
        make_user("buyer1")
        self.client.login(username="buyer1", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("listing:my_listings")).status_code, 403)
        self.assertEqual(self.client.get(reverse("listing:product_create")).status_code, 403)


class ProductDetailTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        self.product = make_product(self.seller)

    def test_detail_publik_untuk_anonim(self):
        response = self.client.get(reverse("listing:product_detail", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Linen blazer krem")
        self.assertContains(response, "Rp85.000")
        self.assertContains(response, reverse("profil_toko:detail", args=["seller1"]))
        self.assertNotContains(response, reverse("listing:product_edit", args=[self.product.pk]))
        self.assertNotContains(response, "owner-actions")

    def test_tombol_aksi_hanya_untuk_pemilik(self):
        make_user("seller2", is_seller=True)
        self.client.login(username="seller2", password=PASSWORD)
        response = self.client.get(reverse("listing:product_detail", args=[self.product.pk]))
        self.assertNotContains(response, "owner-actions")

        self.client.login(username="seller1", password=PASSWORD)
        response = self.client.get(reverse("listing:product_detail", args=[self.product.pk]))
        self.assertContains(response, "owner-actions")
        self.assertContains(response, reverse("listing:product_edit", args=[self.product.pk]))
        self.assertContains(response, reverse("listing:product_mark_sold", args=[self.product.pk]))

    def test_detail_produk_terjual_tetap_bisa_dibuka(self):
        self.product.status = "sold"
        self.product.save()
        response = self.client.get(reverse("listing:product_detail", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dari_toko_yang_sama_maks_4_produk_aktif(self):
        for i in range(5):
            make_product(self.seller, name=f"Lain {i}")
        make_product(self.seller, name="Lain terjual", status="sold")
        response = self.client.get(reverse("listing:product_detail", args=[self.product.pk]))
        same_store = list(response.context["same_store"])
        self.assertEqual(len(same_store), 4)
        self.assertNotIn(self.product, same_store)
        self.assertTrue(all(p.status == "active" for p in same_store))

    def test_detail_404_kalau_tidak_ada(self):
        self.assertEqual(self.client.get(reverse("listing:product_detail", args=[999])).status_code, 404)


class MyListingsFilterTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        make_product(self.seller, name="Blazer aktif", category="outerwear")
        make_product(self.seller, name="Kaos aktif", category="atasan")
        make_product(self.seller, name="Coat terjual", category="outerwear", status="sold")
        self.client.login(username="seller1", password=PASSWORD)
        self.url = reverse("listing:my_listings")

    def names(self, response):
        return {p.name for p in response.context["products"]}

    def test_hitungan_per_status(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["counts"], {"semua": 3, "active": 2, "sold": 1})

    def test_filter_status(self):
        self.assertEqual(self.names(self.client.get(self.url, {"status": "sold"})), {"Coat terjual"})
        self.assertEqual(self.names(self.client.get(self.url, {"status": "active"})), {"Blazer aktif", "Kaos aktif"})

    def test_filter_kategori_dan_kombinasi(self):
        self.assertEqual(self.names(self.client.get(self.url, {"category": "atasan"})), {"Kaos aktif"})
        response = self.client.get(self.url, {"category": "outerwear", "status": "active"})
        self.assertEqual(self.names(response), {"Blazer aktif"})

    def test_filter_invalid_diabaikan(self):
        response = self.client.get(self.url, {"status": "hilang", "category": "xx"})
        self.assertEqual(len(self.names(response)), 3)


class JsonEndpointTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        self.mantan = make_user("mantan", is_seller=False)
        self.active = make_product(self.seller, name="Aktif")
        self.sold = make_product(self.seller, name="Terjual", status="sold")
        make_product(self.mantan, name="Seller nonaktif")

    def test_product_list_json_hanya_publik(self):
        response = self.client.get(reverse("listing:product_list_json"))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
        item = data["products"][0]
        self.assertEqual(item["name"], "Aktif")
        for key in ("id", "price", "price_display", "image_url", "detail_url", "seller", "status"):
            self.assertIn(key, item)

    def test_product_list_json_filter_kategori(self):
        make_product(self.seller, name="Atasan", category="atasan")
        data = self.client.get(reverse("listing:product_list_json"), {"category": "atasan"}).json()
        self.assertEqual([p["name"] for p in data["products"]], ["Atasan"])

    def test_product_detail_json(self):
        data = self.client.get(reverse("listing:product_detail_json", args=[self.sold.pk])).json()
        self.assertTrue(data["success"])
        self.assertEqual(data["product"]["name"], "Terjual")
        self.assertEqual(data["product"]["description"], "Blazer linen potongan regular.")
        self.assertEqual(data["product"]["images"], [])
        self.assertEqual(self.client.get(reverse("listing:product_detail_json", args=[999])).status_code, 404)

    def test_my_products_json_seller_saja(self):
        make_product(make_user("seller2", is_seller=True), name="Punya orang")
        self.client.login(username="seller1", password=PASSWORD)
        data = self.client.get(reverse("listing:my_products_json")).json()
        self.assertEqual({p["name"] for p in data["products"]}, {"Aktif", "Terjual"})
        self.assertEqual(data["counts"]["sold"], 1)
        data = self.client.get(reverse("listing:my_products_json"), {"status": "sold"}).json()
        self.assertEqual([p["name"] for p in data["products"]], ["Terjual"])

        self.client.login(username="mantan", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("listing:my_products_json")).status_code, 403)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SeedListingTests(TestCase):

    def test_seed_tanpa_seller_keluar_rapi(self):
        out = StringIO()
        call_command("seed_listing", stdout=out)
        self.assertIn("seed_akun", out.getvalue())
        self.assertFalse(Product.objects.exists())

    def test_seed_idempoten(self):
        make_user("seller1", is_seller=True)
        make_user("seller2", is_seller=True)
        call_command("seed_listing", stdout=StringIO())
        count = Product.objects.count()
        call_command("seed_listing", stdout=StringIO())
        self.assertEqual(Product.objects.count(), count)
        self.assertGreaterEqual(count, 18)
        self.assertTrue(Product.objects.filter(status="sold").exists())

    def test_seed_membuat_foto_placeholder_sekali(self):
        make_user("seller1", is_seller=True)
        make_user("seller2", is_seller=True)
        call_command("seed_listing", stdout=StringIO())
        total = ProductImage.objects.count()
        self.assertGreaterEqual(total, Product.objects.count())
        self.assertEqual(Product.objects.get(name="Linen blazer krem").images.count(), 3)
        self.assertEqual(Product.objects.get(name="Parka olive").images.count(), 1)
        # Produk yang sudah punya foto tidak ditambah lagi.
        call_command("seed_listing", stdout=StringIO())
        self.assertEqual(ProductImage.objects.count(), total)

    def test_seed_menambah_foto_ke_produk_lama_dan_opsi_no_images(self):
        make_user("seller1", is_seller=True)
        make_user("seller2", is_seller=True)
        call_command("seed_listing", "--no-images", stdout=StringIO())
        self.assertFalse(ProductImage.objects.exists())
        call_command("seed_listing", stdout=StringIO())
        self.assertEqual(Product.objects.filter(images__isnull=True).count(), 0)
        image = ProductImage.objects.first()
        self.assertTrue(image.image.name.endswith(".jpg"))
        self.assertTrue(image.alt_text)
