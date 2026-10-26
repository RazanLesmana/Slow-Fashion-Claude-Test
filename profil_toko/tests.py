from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.test import Client, TestCase
from django.urls import reverse

from akun.models import Profile
from listing.models import Product
from .forms import SizeChartForm, StoreForm
from .models import SizeChart, Store

PASSWORD = "demo12345"

STORE_POST = {
    "name": "Rara Preloved",
    "city": "Jakarta Selatan",
    "description": "Blazer dan outerwear.",
    "whatsapp_number": "0812 3456 7890",
}


def make_user(username, is_seller=False):
    user = User.objects.create_user(username=username, password=PASSWORD)
    Profile.objects.update_or_create(user=user, defaults={"is_seller": is_seller})
    return user


def make_store(user, **kwargs):
    data = {"name": "Rara Preloved", "city": "Jakarta Selatan", "whatsapp_number": "081234567890"}
    data.update(kwargs)
    Profile.objects.update_or_create(user=user, defaults={"is_seller": True})
    return Store.objects.create(owner=user, **data)


def make_product(seller, name="Linen blazer krem", status="active", brand="Uniqlo", size="M"):
    return Product.objects.create(
        seller=seller, name=name, brand=brand, description="Deskripsi",
        category="outerwear", size=size, condition="good",
        price=Decimal("85000"), status=status,
    )


class StoreModelTests(TestCase):

    def test_str_initial_dan_whatsapp_url(self):
        store = make_store(make_user("seller1"))
        self.assertEqual(str(store), "Rara Preloved")
        self.assertEqual(store.initial, "R")
        self.assertEqual(store.whatsapp_url, "https://wa.me/6281234567890")

    def test_satu_user_satu_toko(self):
        user = make_user("seller1")
        make_store(user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Store.objects.create(owner=user, name="Toko kedua", city="Depok", whatsapp_number="081111111111")

    def test_validasi_nomor_whatsapp(self):
        store = Store(owner=make_user("seller1"), name="A", city="B", whatsapp_number="12345")
        with self.assertRaises(ValidationError):
            store.full_clean()
        for number in ("081234567890", "6281234567890"):
            store.whatsapp_number = number
            store.full_clean()

    def test_store_form_menormalkan_nomor(self):
        form = StoreForm({**STORE_POST, "whatsapp_number": "+62 812-3456-7890"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["whatsapp_number"], "6281234567890")
        form = StoreForm({**STORE_POST, "whatsapp_number": "0712 3456"})
        self.assertFalse(form.is_valid())
        self.assertIn("whatsapp_number", form.errors)


class BukaTokoTests(TestCase):

    def setUp(self):
        self.user = make_user("budi")
        self.client.login(username="budi", password=PASSWORD)

    def test_buka_toko_mengaktifkan_seller(self):
        response = self.client.post(reverse("profil_toko:buka_toko"), STORE_POST)
        self.assertRedirects(response, reverse("profil_toko:detail", args=["budi"]))
        store = Store.objects.get(owner=self.user)
        self.assertEqual(store.whatsapp_number, "081234567890")
        self.assertTrue(Profile.objects.get(user=self.user).is_seller)

    def test_buka_toko_untuk_user_tanpa_profile(self):
        Profile.objects.filter(user=self.user).delete()
        self.client.post(reverse("profil_toko:buka_toko"), STORE_POST)
        self.assertTrue(Profile.objects.get(user=self.user).is_seller)

    def test_sudah_punya_toko_diarahkan_ke_toko_saya(self):
        make_store(self.user)
        response = self.client.get(reverse("profil_toko:buka_toko"))
        self.assertRedirects(response, reverse("profil_toko:toko_saya"), fetch_redirect_response=False)
        self.client.post(reverse("profil_toko:buka_toko"), {**STORE_POST, "name": "Kedua"})
        self.assertEqual(Store.objects.filter(owner=self.user).count(), 1)

    def test_toko_saya(self):
        response = self.client.get(reverse("profil_toko:toko_saya"))
        self.assertRedirects(response, reverse("profil_toko:buka_toko"))
        make_store(self.user)
        response = self.client.get(reverse("profil_toko:toko_saya"))
        self.assertRedirects(response, reverse("profil_toko:detail", args=["budi"]))

    def test_form_invalid_tidak_membuat_toko(self):
        response = self.client.post(reverse("profil_toko:buka_toko"), {**STORE_POST, "name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "field-error")
        self.assertFalse(Store.objects.exists())

    def test_anonim_diarahkan_ke_login(self):
        self.client.logout()
        for name in ("profil_toko:buka_toko", "profil_toko:toko_saya"):
            response = self.client.get(reverse(name))
            self.assertTrue(response.url.startswith(reverse("akun:login")))


class StoreDetailTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller1")
        self.store = make_store(self.seller, description="Kebanyakan blazer.")
        make_product(self.seller, name="Blazer aktif")
        make_product(self.seller, name="Coat terjual", status="sold")
        self.url = reverse("profil_toko:detail", args=["seller1"])

    def test_detail_publik(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rara Preloved")
        self.assertContains(response, "Jakarta Selatan")
        self.assertContains(response, "Blazer aktif")
        self.assertContains(response, "Coat terjual")
        self.assertEqual(response.context["counts"], {"semua": 2, "tersedia": 1, "terjual": 1})
        self.assertEqual(response.context["store_owner"], self.seller)

    def test_whatsapp_tersembunyi_untuk_anonim(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "wa.me")
        self.assertNotContains(response, "081234567890")
        self.assertContains(response, "Masuk untuk chat seller")
        self.assertContains(response, reverse("akun:login") + "?next=")

    def test_whatsapp_tampil_untuk_user_login(self):
        make_user("buyer1")
        self.client.login(username="buyer1", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertContains(response, "https://wa.me/6281234567890")
        self.assertNotContains(response, "store-edit-form")

    def test_pemilik_melihat_form_edit(self):
        self.client.login(username="seller1", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertContains(response, "store-edit-form")
        self.assertContains(response, reverse("profil_toko:tutup_toko", args=["seller1"]))

    def test_toko_tidak_ada_404(self):
        self.assertEqual(self.client.get(reverse("profil_toko:detail", args=["siapa"])).status_code, 404)

    def test_tab_json_per_status(self):
        url = reverse("profil_toko:store_products_json", args=["seller1"])
        names = lambda status: [p["name"] for p in self.client.get(url, {"status": status}).json()["products"]]
        self.assertEqual(set(names("semua")), {"Blazer aktif", "Coat terjual"})
        self.assertEqual(names("tersedia"), ["Blazer aktif"])
        self.assertEqual(names("terjual"), ["Coat terjual"])
        data = self.client.get(url, {"status": "aneh"}).json()
        self.assertEqual(data["status"], "semua")
        self.assertEqual(data["counts"]["terjual"], 1)
        product = data["products"][0]
        for key in ("id", "price_display", "detail_url", "image_url", "status"):
            self.assertIn(key, product)

    def test_store_json_whatsapp_hanya_untuk_login(self):
        url = reverse("profil_toko:store_json", args=["seller1"])
        data = self.client.get(url).json()
        self.assertEqual(data["store"]["name"], "Rara Preloved")
        self.assertNotIn("whatsapp_number", data["store"])
        self.assertNotIn("whatsapp_url", data["store"])

        make_user("buyer1")
        self.client.login(username="buyer1", password=PASSWORD)
        data = self.client.get(url).json()
        self.assertEqual(data["store"]["whatsapp_number"], "081234567890")


class EditTutupTokoTests(TestCase):

    def setUp(self):
        self.owner = make_user("seller1")
        self.store = make_store(self.owner)
        make_product(self.owner)
        self.other = make_user("seller2")
        make_store(self.other, name="Toko Lain")
        self.edit_url = reverse("profil_toko:edit", args=["seller1"])
        self.close_url = reverse("profil_toko:tutup_toko", args=["seller1"])

    def test_edit_oleh_pemilik(self):
        self.client.login(username="seller1", password=PASSWORD)
        response = self.client.post(self.edit_url, {**STORE_POST, "name": "Nama Baru", "city": "Depok"})
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["store"]["name"], "Nama Baru")
        self.store.refresh_from_db()
        self.assertEqual(self.store.city, "Depok")

    def test_edit_invalid_400(self):
        self.client.login(username="seller1", password=PASSWORD)
        response = self.client.post(self.edit_url, {**STORE_POST, "whatsapp_number": "123"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("whatsapp_number", response.json()["errors"])

    def test_edit_dan_tutup_oleh_user_lain_403(self):
        self.client.login(username="seller2", password=PASSWORD)
        self.assertEqual(self.client.post(self.edit_url, {**STORE_POST, "name": "Hack"}).status_code, 403)
        self.assertEqual(self.client.post(self.close_url).status_code, 403)
        self.store.refresh_from_db()
        self.assertEqual(self.store.name, "Rara Preloved")

    def test_anonim_dan_get_ditolak(self):
        self.assertEqual(self.client.post(self.edit_url, STORE_POST).status_code, 302)
        self.assertEqual(self.client.post(self.close_url).status_code, 302)
        self.client.login(username="seller1", password=PASSWORD)
        self.assertEqual(self.client.get(self.close_url).status_code, 405)
        self.assertTrue(Store.objects.filter(pk=self.store.pk).exists())

    def test_tutup_toko_menonaktifkan_seller(self):
        self.client.login(username="seller1", password=PASSWORD)
        data = self.client.post(self.close_url).json()
        self.assertTrue(data["success"])
        self.assertFalse(Store.objects.filter(owner=self.owner).exists())
        self.assertFalse(Profile.objects.get(user=self.owner).is_seller)
        # Produk tetap ada di DB, tapi tidak lagi publik.
        self.assertEqual(Product.objects.filter(seller=self.owner).count(), 1)
        self.assertFalse(Product.objects.public().filter(seller=self.owner).exists())

    def test_edit_butuh_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="seller1", password=PASSWORD)
        self.assertEqual(client.post(self.edit_url, STORE_POST).status_code, 403)


class SizeChartTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        self.other = make_user("seller2", is_seller=True)
        self.chart = SizeChart.objects.create(brand="Uniqlo", size="M", chest_cm=102, length_cm=72, created_by=self.seller)
        SizeChart.objects.create(brand="Uniqlo", size="S", chest_cm=96, length_cm=70, created_by=self.seller)
        SizeChart.objects.create(brand="Zara", size="M", chest_cm=100, length_cm=70, created_by=self.other)

    def test_str(self):
        self.assertEqual(str(self.chart), "Uniqlo M")

    def test_unique_brand_case_insensitive(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SizeChart.objects.create(brand="uniqlo", size="m", chest_cm=1, length_cm=1)
        form = SizeChartForm({"brand": "UNIQLO", "size": "m", "chest_cm": 100, "length_cm": 70})
        self.assertFalse(form.is_valid())
        self.assertIn("Size chart untuk brand dan size ini sudah ada.", str(form.errors))

    def test_list_publik_dan_filter_brand(self):
        response = self.client.get(reverse("profil_toko:size_chart_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([g["brand"] for g in response.context["groups"]], ["Uniqlo", "Zara"])
        response = self.client.get(reverse("profil_toko:size_chart_list"), {"brand": "uniqlo"})
        groups = response.context["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual([c.size for c in groups[0]["rows"]], ["S", "M"])

    def test_json_filter_brand(self):
        data = self.client.get(reverse("profil_toko:size_chart_json"), {"brand": "Uniqlo"}).json()
        self.assertTrue(data["success"])
        self.assertEqual([(c["brand"], c["size"]) for c in data["size_charts"]], [("Uniqlo", "S"), ("Uniqlo", "M")])
        data = self.client.get(reverse("profil_toko:size_chart_json")).json()
        self.assertEqual(data["count"], 3)

    def test_create_oleh_seller(self):
        self.client.login(username="seller2", password=PASSWORD)
        response = self.client.post(reverse("profil_toko:size_chart_create"),
                                    {"brand": "Mango", "size": "l", "chest_cm": 102, "length_cm": 68})
        self.assertEqual(response.status_code, 302)
        chart = SizeChart.objects.get(brand="Mango")
        self.assertEqual(chart.size, "L")
        self.assertEqual(chart.created_by, self.other)

    def test_create_ditolak_untuk_anonim_dan_buyer(self):
        response = self.client.get(reverse("profil_toko:size_chart_create"))
        self.assertTrue(response.url.startswith(reverse("akun:login")))
        make_user("buyer1")
        self.client.login(username="buyer1", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("profil_toko:size_chart_create")).status_code, 403)

    def test_edit_hanya_pembuat_atau_superuser(self):
        url = reverse("profil_toko:size_chart_edit", args=[self.chart.pk])
        data = {"brand": "Uniqlo", "size": "M", "chest_cm": 104, "length_cm": 73}
        self.client.login(username="seller2", password=PASSWORD)
        self.assertEqual(self.client.post(url, data).status_code, 403)

        self.client.login(username="seller1", password=PASSWORD)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.chart.refresh_from_db()
        self.assertEqual(self.chart.chest_cm, 104)

        admin = User.objects.create_superuser("admin", "a@example.com", PASSWORD)
        Profile.objects.update_or_create(user=admin, defaults={"is_seller": True})
        self.client.login(username="admin", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_hapus_via_ajax(self):
        url = reverse("profil_toko:size_chart_delete", args=[self.chart.pk])
        self.client.login(username="seller2", password=PASSWORD)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["success"])

        self.client.login(username="seller1", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(self.client.post(url).json()["success"])
        self.assertFalse(SizeChart.objects.filter(pk=self.chart.pk).exists())


class SizeChartSlotTests(TestCase):

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        for size, chest in (("S", 96), ("M", 102), ("L", 108)):
            SizeChart.objects.create(brand="Uniqlo", size=size, chest_cm=chest, length_cm=70)

    def test_slot_highlight_size_yang_cocok(self):
        product = make_product(self.seller, brand="uniqlo", size="m")
        html = render_to_string("profil_toko/slots/size_chart.html", {"product": product})
        self.assertIn("Size chart uniqlo", html)
        self.assertEqual(html.count('class="is-selected"'), 1)
        selected_row = html.split('class="is-selected"')[1].split("</tr>")[0]
        self.assertIn("102 cm", selected_row)

    def test_slot_brand_tanpa_data(self):
        product = make_product(self.seller, brand="Zara")
        html = render_to_string("profil_toko/slots/size_chart.html", {"product": product})
        self.assertIn("Size chart untuk brand ini belum tersedia.", html)
        self.assertNotIn("<table", html)


class SeedTokoTests(TestCase):

    def test_seed_tanpa_seller_keluar_rapi(self):
        out = StringIO()
        call_command("seed_toko", stdout=out)
        self.assertIn("seed_akun", out.getvalue())
        self.assertFalse(Store.objects.exists())

    def test_seed_idempoten(self):
        make_user("seller1", is_seller=True)
        make_user("seller2", is_seller=True)
        call_command("seed_toko", stdout=StringIO())
        call_command("seed_toko", stdout=StringIO())
        self.assertEqual(Store.objects.count(), 2)
        self.assertEqual(Store.objects.get(owner__username="seller1").name, "Rara Preloved")
        self.assertEqual(SizeChart.objects.count(), 16)
        self.assertEqual(set(SizeChart.objects.values_list("brand", flat=True)), {"Uniqlo", "Zara", "H&M", "Mango"})
