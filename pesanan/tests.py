from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import AnonymousUser, User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from akun.models import Profile
from listing.models import Product
from .constants import SHIPPING_FEE_PER_STORE
from .context_processors import cart_count
from .forms import CheckoutForm
from .models import CartItem, Order, OrderItem

PASSWORD = "demo12345"

ADDRESS = {
    "recipient_name": "Budi Pembeli",
    "phone": "0812 3456 7890",
    "address": "Jl. Margonda Raya No. 1",
    "city": "Depok",
    "postal_code": "16424",
    "payment_method": "transfer",
}


def make_user(username, is_seller=False):
    user = User.objects.create_user(username=username, password=PASSWORD)
    Profile.objects.update_or_create(user=user, defaults={"is_seller": is_seller})
    # Ambil ulang: signal akun menyimpan cache user.profile lama (is_seller=False).
    return User.objects.get(pk=user.pk)


def make_product(seller, name, price="85000", status="active"):
    return Product.objects.create(
        seller=seller, name=name, brand="Uniqlo", description="Deskripsi", category="outerwear",
        size="M", condition="good", price=Decimal(price), status=status,
    )


class PesananTestMixin:

    def setUp(self):
        self.seller1 = make_user("seller1", is_seller=True)
        self.seller2 = make_user("seller2", is_seller=True)
        self.buyer = make_user("buyer1")
        self.other = make_user("buyer2")
        self.blazer = make_product(self.seller1, "Linen blazer krem", "85000")
        self.top = make_product(self.seller1, "Ribbed knit top hitam", "45000")
        self.jeans = make_product(self.seller2, "501 jeans light wash", "120000")
        self.client.login(username="buyer1", password=PASSWORD)

    def add(self, product, client=None):
        return (client or self.client).post(reverse("pesanan:cart_add", args=[product.pk]))

    def checkout(self, products, **overrides):
        data = {**ADDRESS, **overrides, "product_ids": [p.pk for p in products]}
        return self.client.post(reverse("pesanan:checkout"), data)

    def make_order(self, products):
        for product in products:
            CartItem.objects.get_or_create(user=self.buyer, product=product)
        self.checkout(products)
        return Order.objects.filter(buyer=self.buyer).order_by("-pk").first()


class ModelTests(PesananTestMixin, TestCase):

    def test_cart_item_unik(self):
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(user=self.buyer, product=self.blazer)

    def test_kode_dan_total_order(self):
        first = Order.objects.create(
            buyer=self.buyer, seller=self.seller1, subtotal=Decimal("85000"), shipping_fee=SHIPPING_FEE_PER_STORE,
            recipient_name="A", phone="081234567890", address="X", city="Y", postal_code="12345",
        )
        second = Order.objects.create(
            buyer=self.buyer, seller=self.seller1, subtotal=Decimal("1000"), shipping_fee=SHIPPING_FEE_PER_STORE,
            recipient_name="A", phone="081234567890", address="X", city="Y", postal_code="12345",
        )
        first.refresh_from_db()
        self.assertEqual(first.code, f"LPK-{first.pk:04d}")
        self.assertNotEqual(first.code, second.code)
        self.assertEqual(first.total, Decimal("100000"))
        first.save()
        first.refresh_from_db()
        self.assertEqual(first.code, f"LPK-{first.pk:04d}")
        self.assertEqual(str(first), first.code)

    def test_checkout_form_validasi(self):
        form = CheckoutForm({**ADDRESS, "phone": "12345", "postal_code": "1642"})
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)
        self.assertIn("postal_code", form.errors)
        form = CheckoutForm({**ADDRESS, "phone": "+62 812-3456-7890"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "6281234567890")


class CartAddTests(PesananTestMixin, TestCase):

    def test_tambah_sukses(self):
        response = self.add(self.blazer)
        data = response.json()
        self.assertEqual((response.status_code, data["success"], data["cart_count"]), (200, True, 1))
        self.assertTrue(CartItem.objects.filter(user=self.buyer, product=self.blazer).exists())

    def test_duplikat_ditolak(self):
        self.add(self.blazer)
        response = self.add(self.blazer)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Barang ini sudah ada di keranjang.")
        self.assertEqual(CartItem.objects.count(), 1)

    def test_produk_sendiri_sold_dan_seller_nonaktif_ditolak(self):
        self.client.login(username="seller1", password=PASSWORD)
        self.assertEqual(self.add(self.blazer).status_code, 400)
        self.client.login(username="buyer1", password=PASSWORD)
        sold = make_product(self.seller1, "Sudah laku", status="sold")
        self.assertEqual(self.add(sold).json()["message"], "Barang ini sudah terjual.")
        Profile.objects.filter(user=self.seller2).update(is_seller=False)
        self.assertEqual(self.add(self.jeans).json()["message"], "Toko ini sedang tidak aktif.")
        self.assertFalse(CartItem.objects.exists())

    def test_anonim_dan_get(self):
        self.assertEqual(self.client.get(reverse("pesanan:cart_add", args=[self.blazer.pk])).status_code, 405)
        self.client.logout()
        response = self.add(self.blazer)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("akun:login")))

    def test_csrf_wajib(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="buyer1", password=PASSWORD)
        self.assertEqual(self.add(self.blazer, client).status_code, 403)
        self.assertFalse(CartItem.objects.exists())


class CartPageTests(PesananTestMixin, TestCase):

    def test_keranjang_dikelompokkan_dan_tidak_tersedia_dipisah(self):
        for product in (self.blazer, self.top, self.jeans):
            CartItem.objects.create(user=self.buyer, product=product)
        sold = make_product(self.seller2, "Barang laku", "50000")
        CartItem.objects.create(user=self.buyer, product=sold)
        Product.objects.filter(pk=sold.pk).update(status="sold")

        response = self.client.get(reverse("pesanan:keranjang"))
        cart = response.context["cart"]
        self.assertEqual(cart["item_count"], 3)
        self.assertEqual(cart["store_count"], 2)
        self.assertEqual(cart["subtotal"], Decimal("250000"))
        self.assertEqual([i.product.name for i in cart["unavailable"]], ["Barang laku"])
        self.assertContains(response, "Tidak tersedia lagi")
        self.assertContains(response, "3</span> barang dari <span data-summary=\"store_count\">2")

    def test_hapus_item_pemilik(self):
        a = CartItem.objects.create(user=self.buyer, product=self.blazer)
        CartItem.objects.create(user=self.buyer, product=self.jeans)
        data = self.client.post(reverse("pesanan:cart_remove", args=[a.pk])).json()
        self.assertTrue(data["success"])
        self.assertEqual(
            (data["item_count"], data["store_count"], data["subtotal"], data["cart_count"]),
            (1, 1, 120000, 1),
        )
        self.assertEqual(data["subtotal_display"], "Rp120.000")
        self.assertFalse(CartItem.objects.filter(pk=a.pk).exists())

    def test_hapus_item_user_lain_404(self):
        item = CartItem.objects.create(user=self.other, product=self.blazer)
        self.assertEqual(self.client.post(reverse("pesanan:cart_remove", args=[item.pk])).status_code, 404)
        self.assertTrue(CartItem.objects.filter(pk=item.pk).exists())

    def test_cart_json(self):
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        CartItem.objects.create(user=self.other, product=self.top)
        sold = make_product(self.seller1, "Laku", status="sold")
        CartItem.objects.create(user=self.buyer, product=sold)
        data = self.client.get(reverse("pesanan:cart_json")).json()
        self.assertEqual([i["name"] for i in data["items"]], ["Linen blazer krem"])
        self.assertEqual([i["name"] for i in data["unavailable"]], ["Laku"])
        self.assertEqual(data["cart_count"], 1)
        self.assertEqual(data["subtotal"], 85000)


class CheckoutTests(PesananTestMixin, TestCase):

    def test_get_checkout_dengan_prefill(self):
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        response = self.client.get(reverse("pesanan:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pembayaran di aplikasi ini hanya simulasi.")
        self.assertContains(response, "Bayar sekarang")
        self.make_order([self.blazer])
        CartItem.objects.create(user=self.buyer, product=self.top)
        response = self.client.get(reverse("pesanan:checkout"))
        self.assertEqual(response.context["form"].initial["city"], "Depok")

    def test_satu_toko(self):
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        CartItem.objects.create(user=self.buyer, product=self.top)
        response = self.checkout([self.blazer, self.top])
        order = Order.objects.get()
        self.assertRedirects(response, reverse("pesanan:checkout_success", args=[order.checkout_ref]))
        self.assertEqual(order.subtotal, Decimal("130000"))
        self.assertEqual(order.total, Decimal("145000"))
        self.assertEqual(order.status, "diproses")
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(order.phone, "081234567890")
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(set(Product.objects.filter(pk__in=[self.blazer.pk, self.top.pk]).values_list("status", flat=True)), {"sold"})
        self.assertFalse(CartItem.objects.filter(user=self.buyer).exists())

    def test_dua_toko(self):
        for product in (self.blazer, self.jeans):
            CartItem.objects.create(user=self.buyer, product=product)
        CartItem.objects.create(user=self.other, product=self.jeans)
        self.checkout([self.blazer, self.jeans])
        orders = list(Order.objects.order_by("pk"))
        self.assertEqual(len(orders), 2)
        self.assertEqual({o.seller for o in orders}, {self.seller1, self.seller2})
        self.assertTrue(all(o.shipping_fee == Decimal("15000") for o in orders))
        self.assertEqual(orders[0].checkout_ref, orders[1].checkout_ref)
        # Keranjang user lain tidak dihapus; barangnya pindah ke grup "Tidak tersedia lagi".
        self.assertTrue(CartItem.objects.filter(user=self.other, product=self.jeans).exists())

        response = self.client.get(reverse("pesanan:checkout_success", args=[orders[0].checkout_ref]))
        self.assertContains(response, orders[0].code)
        self.assertContains(response, orders[1].code)
        self.assertEqual(response.context["grand_total"], Decimal("235000"))
        self.assertContains(response, "Rp235.000")

    def test_produk_keburu_sold_tidak_ada_order(self):
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        CartItem.objects.create(user=self.buyer, product=self.jeans)
        Product.objects.filter(pk=self.jeans.pk).update(status="sold")
        response = self.checkout([self.blazer, self.jeans])
        self.assertRedirects(response, reverse("pesanan:keranjang"), fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Product.objects.get(pk=self.blazer.pk).status, "active")
        follow = self.client.get(reverse("pesanan:keranjang"))
        self.assertContains(follow, "501 jeans light wash")
        self.assertEqual(CartItem.objects.filter(user=self.buyer).count(), 2)

    def test_keranjang_kosong_redirect(self):
        self.assertRedirects(self.client.get(reverse("pesanan:checkout")), reverse("pesanan:keranjang"))
        response = self.client.post(reverse("pesanan:checkout"), ADDRESS)
        self.assertRedirects(response, reverse("pesanan:keranjang"))
        self.assertFalse(Order.objects.exists())

    def test_form_invalid_tidak_membuat_order(self):
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        response = self.checkout([self.blazer], phone="123", postal_code="abcde")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No. HP harus diawali 08 atau 62")
        self.assertContains(response, "Kode pos harus 5 digit angka.")
        self.assertFalse(Order.objects.exists())

    def test_halaman_sukses_orang_lain_404(self):
        order = self.make_order([self.blazer])
        self.client.login(username="buyer2", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("pesanan:checkout_success", args=[order.checkout_ref])).status_code, 404)


class StatusTests(PesananTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.order = self.make_order([self.blazer, self.top])

    def post(self, name, username):
        self.client.login(username=username, password=PASSWORD)
        return self.client.post(reverse(name, args=[self.order.code]))

    def test_alur_kirim_lalu_selesai(self):
        data = self.post("pesanan:order_ship", "seller1").json()
        self.assertEqual((data["success"], data["order"]["status"]), (True, "dikirim"))
        self.assertEqual(data["counts"]["dikirim"], 1)
        data = self.post("pesanan:order_complete", "buyer1").json()
        self.assertEqual(data["order"]["status"], "selesai")
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.shipped_at)
        self.assertIsNotNone(self.order.completed_at)

    def test_transisi_ilegal_ditolak(self):
        self.assertEqual(self.post("pesanan:order_complete", "buyer1").status_code, 400)  # selesai dari diproses
        self.assertEqual(self.post("pesanan:order_ship", "buyer1").status_code, 400)      # kirim oleh buyer
        self.assertEqual(self.post("pesanan:order_complete", "seller1").status_code, 400)  # selesai oleh seller
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "diproses")

    def test_batal_oleh_buyer_produk_kembali_active(self):
        data = self.post("pesanan:order_cancel", "buyer1").json()
        self.assertEqual(data["order"]["status"], "dibatalkan")
        self.order.refresh_from_db()
        self.assertEqual(self.order.cancelled_by, self.buyer)
        self.assertEqual(set(Product.objects.filter(pk__in=[self.blazer.pk, self.top.pk]).values_list("status", flat=True)), {"active"})

    def test_batal_oleh_seller_dan_produk_terhapus(self):
        Product.objects.filter(pk=self.top.pk).delete()
        self.assertTrue(self.post("pesanan:order_cancel", "seller1").json()["success"])
        self.assertEqual(Product.objects.get(pk=self.blazer.pk).status, "active")
        self.assertEqual(OrderItem.objects.filter(order=self.order).count(), 2)  # riwayat tetap ada

    def test_batal_saat_dikirim_ditolak(self):
        self.post("pesanan:order_ship", "seller1")
        self.assertEqual(self.post("pesanan:order_cancel", "buyer1").status_code, 400)
        self.assertEqual(Product.objects.get(pk=self.blazer.pk).status, "sold")

    def test_user_lain_404_dan_post_only(self):
        for name in ("pesanan:order_ship", "pesanan:order_complete", "pesanan:order_cancel"):
            self.assertEqual(self.post(name, "buyer2").status_code, 404, name)
            self.assertEqual(self.post(name, "seller2").status_code, 404, name)
        self.client.login(username="seller1", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("pesanan:order_ship", args=[self.order.code])).status_code, 405)


class AccessAndJsonTests(PesananTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.order = self.make_order([self.blazer])
        self.order2 = self.make_order([self.jeans])
        Order.objects.filter(pk=self.order2.pk).update(status="dikirim")

    def test_detail_hanya_buyer_dan_seller(self):
        url = reverse("pesanan:order_detail", args=[self.order.code])
        response = self.client.get(url)
        self.assertContains(response, "Jl. Margonda Raya No. 1")
        self.assertContains(response, "081234567890")
        self.client.login(username="seller1", password=PASSWORD)
        self.assertContains(self.client.get(url), "081234567890")
        for username in ("buyer2", "seller2"):
            self.client.login(username=username, password=PASSWORD)
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_pesanan_masuk_hanya_seller(self):
        self.assertEqual(self.client.get(reverse("pesanan:pesanan_masuk")).status_code, 403)
        self.client.login(username="seller1", password=PASSWORD)
        response = self.client.get(reverse("pesanan:pesanan_masuk"))
        self.assertContains(response, self.order.code)
        self.assertNotContains(response, self.order2.code)
        self.assertContains(response, "Tandai dikirim")

    def test_pesanan_saya_tab_counts(self):
        response = self.client.get(reverse("pesanan:pesanan_saya"))
        self.assertContains(response, self.order.code)
        self.assertContains(response, self.order2.code)
        self.assertEqual(response.context["counts"]["semua"], 2)
        self.assertContains(response, "Pesanan diterima")

    def test_orders_json_role_dan_status(self):
        url = reverse("pesanan:orders_json")
        data = self.client.get(url).json()
        self.assertEqual(data["role"], "buyer")
        self.assertEqual(len(data["orders"]), 2)
        self.assertEqual(data["counts"], {"diproses": 1, "dikirim": 1, "selesai": 0, "dibatalkan": 0, "semua": 2})
        data = self.client.get(url, {"status": "dikirim"}).json()
        self.assertEqual([o["code"] for o in data["orders"]], [self.order2.code])
        self.assertIn("shipping_address", data["orders"][0])
        self.assertIsNotNone(data["orders"][0]["actions"]["complete"])

        self.assertEqual(self.client.get(url, {"role": "seller"}).status_code, 403)
        self.client.login(username="seller1", password=PASSWORD)
        data = self.client.get(url, {"role": "seller"}).json()
        self.assertEqual([o["code"] for o in data["orders"]], [self.order.code])
        self.assertIsNotNone(data["orders"][0]["actions"]["ship"])

    def test_alamat_tidak_bocor_ke_user_lain(self):
        self.client.login(username="buyer2", password=PASSWORD)
        response = self.client.get(reverse("pesanan:orders_json"))
        self.assertEqual(response.json()["orders"], [])
        self.assertNotContains(response, "Margonda")
        self.assertNotContains(response, "081234567890")
        # seller2 hanya melihat pesanan masuk miliknya, bukan pesanan seller1.
        self.client.login(username="seller2", password=PASSWORD)
        data = self.client.get(reverse("pesanan:orders_json"), {"role": "seller"}).json()
        self.assertEqual([o["code"] for o in data["orders"]], [self.order2.code])
        self.assertNotIn(self.order.code, str(data))

    def test_anonim_diarahkan_login(self):
        self.client.logout()
        for name in ("pesanan:keranjang", "pesanan:checkout", "pesanan:pesanan_saya", "pesanan:pesanan_masuk",
                     "pesanan:cart_json", "pesanan:orders_json"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertTrue(response.url.startswith(reverse("akun:login")), name)


class SlotAndContextTests(PesananTestMixin, TestCase):

    def render_slot(self, user, product):
        request = RequestFactory().get(f"/listing/{product.pk}/")
        request.user = user
        return render_to_string("pesanan/slots/add_to_cart.html", {"product": product, "user": user}, request=request)

    def test_slot_per_kondisi(self):
        html = self.render_slot(AnonymousUser(), self.blazer)
        self.assertIn("Masuk untuk membeli", html)
        self.assertIn(reverse("akun:login") + f"?next=/listing/{self.blazer.pk}/", html)
        self.assertNotIn("Tambah ke keranjang", self.render_slot(self.seller1, self.blazer))
        self.assertNotIn("Masuk untuk membeli", self.render_slot(self.seller1, self.blazer))
        self.assertIn("Tambah ke keranjang", self.render_slot(self.buyer, self.blazer))
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        self.assertIn("Lihat keranjang", self.render_slot(self.buyer, self.blazer))
        sold = make_product(self.seller1, "Laku", status="sold")
        html = self.render_slot(self.buyer, sold)
        self.assertIn("Terjual", html)
        self.assertIn("disabled", html)

    def test_slot_di_detail_produk(self):
        response = self.client.get(reverse("listing:product_detail", args=[self.blazer.pk]))
        self.assertContains(response, "Tambah ke keranjang")
        self.assertContains(response, "pesanan/pesanan.js", count=1)

    def test_context_processor_cart_count(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        self.assertEqual(cart_count(request), {"cart_count": 0})
        CartItem.objects.create(user=self.buyer, product=self.blazer)
        CartItem.objects.create(user=self.buyer, product=make_product(self.seller1, "Laku", status="sold"))
        request.user = self.buyer
        with self.assertNumQueries(1):
            self.assertEqual(cart_count(request), {"cart_count": 1})
        response = self.client.get(reverse("landing"))
        self.assertRegex(response.content.decode(), r"data-cart-count\s*>1<")


class SeedPesananTests(TestCase):

    def test_seed_tanpa_prasyarat(self):
        out = StringIO()
        call_command("seed_pesanan", stdout=out)
        self.assertIn("seed_akun", out.getvalue())

    def test_seed_idempoten(self):
        call_command("seed_akun", stdout=StringIO())
        call_command("seed_listing", "--no-images", stdout=StringIO())
        call_command("seed_pesanan", stdout=StringIO())
        call_command("seed_pesanan", stdout=StringIO())
        buyer = User.objects.get(username="buyer1")
        statuses = sorted(Order.objects.filter(buyer=buyer).values_list("status", flat=True))
        self.assertEqual(statuses, ["dibatalkan", "dikirim", "diproses", "selesai", "selesai"])
        self.assertEqual(Product.objects.get(name="Blazer hitam").status, "sold")
        self.assertEqual(Product.objects.get(name="Bomber jacket olive").status, "active")
        self.assertEqual(CartItem.objects.filter(user=buyer).count(), 3)
