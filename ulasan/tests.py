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
from .forms import ReviewForm
from .models import Review

PASSWORD = "demo12345"


def make_user(username, is_seller=False):
    user = User.objects.create_user(username=username, password=PASSWORD)
    Profile.objects.update_or_create(user=user, defaults={"is_seller": is_seller})
    return user


def make_product(seller, name="Linen blazer krem"):
    return Product.objects.create(
        seller=seller, name=name, brand="Uniqlo", description="Deskripsi",
        category="outerwear", size="M", condition="good", price=Decimal("85000"),
    )


class ReviewTestMixin:

    def setUp(self):
        self.seller = make_user("seller1", is_seller=True)
        self.buyer = make_user("buyer1")
        self.other = make_user("buyer2")
        self.product = make_product(self.seller)


class ReviewModelTests(ReviewTestMixin, TestCase):

    def test_str(self):
        review = Review.objects.create(author=self.buyer, product=self.product, rating=5, comment="Bagus")
        self.assertEqual(str(review), "buyer1 → Linen blazer krem (5★)")
        review = Review.objects.create(author=self.buyer, seller=self.seller, rating=4, comment="Ramah")
        self.assertEqual(str(review), "buyer1 → toko seller1 (4★)")

    def test_tepat_satu_target(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(author=self.buyer, rating=5, comment="Tanpa target")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(author=self.buyer, product=self.product, seller=self.seller, rating=5, comment="Dua target")

    def test_rating_1_sampai_5(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(author=self.buyer, product=self.product, rating=6, comment="x")

    def test_unik_per_author_dan_target(self):
        Review.objects.create(author=self.buyer, product=self.product, rating=5, comment="A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(author=self.buyer, product=self.product, rating=4, comment="B")
        Review.objects.create(author=self.buyer, seller=self.seller, rating=5, comment="C")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(author=self.buyer, seller=self.seller, rating=3, comment="D")
        # Author lain dan target lain tetap boleh.
        Review.objects.create(author=self.other, product=self.product, rating=3, comment="E")
        Review.objects.create(author=self.buyer, product=make_product(self.seller, "Lain"), rating=3, comment="F")

    def test_form_tolak_milik_sendiri(self):
        form = ReviewForm({"rating": 5, "comment": "Mantap"}, author=self.seller, product=self.product)
        self.assertFalse(form.is_valid())
        self.assertIn("Kamu tidak bisa mengulas produkmu sendiri.", form.non_field_errors())
        form = ReviewForm({"rating": 5, "comment": "Mantap"}, author=self.seller, seller=self.seller)
        self.assertIn("Kamu tidak bisa mengulas tokomu sendiri.", form.non_field_errors())

    def test_form_validasi_rating_dan_komentar(self):
        form = ReviewForm({"rating": 0, "comment": "  "}, author=self.buyer, product=self.product)
        self.assertFalse(form.is_valid())
        self.assertIn("rating", form.errors)
        self.assertIn("comment", form.errors)


class CreateReviewTests(ReviewTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client.login(username="buyer1", password=PASSWORD)
        self.product_url = reverse("ulasan:create_product_review", args=[self.product.pk])
        self.store_url = reverse("ulasan:create_store_review", args=["seller1"])

    def test_buat_ulasan_produk_via_ajax(self):
        response = self.client.post(self.product_url, {"rating": 4, "comment": "Sesuai foto"})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["review"]["author"], "buyer1")
        self.assertTrue(data["review"]["is_owner"])
        self.assertEqual(data["summary"], {"average": 4.0, "count": 1})
        review = Review.objects.get()
        self.assertEqual((review.author, review.product, review.seller), (self.buyer, self.product, None))

    def test_buat_ulasan_toko(self):
        data = self.client.post(self.store_url, {"rating": 5, "comment": "Ramah"}).json()
        self.assertTrue(data["success"])
        self.assertEqual(Review.objects.get().seller, self.seller)

    def test_tidak_bisa_dua_kali(self):
        self.client.post(self.product_url, {"rating": 4, "comment": "Pertama"})
        response = self.client.post(self.product_url, {"rating": 5, "comment": "Kedua"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Kamu sudah mengulas produk ini.")
        self.assertEqual(Review.objects.count(), 1)

    def test_tidak_bisa_mengulas_milik_sendiri(self):
        self.client.login(username="seller1", password=PASSWORD)
        response = self.client.post(self.product_url, {"rating": 5, "comment": "Produkku"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Kamu tidak bisa mengulas produkmu sendiri.")
        response = self.client.post(self.store_url, {"rating": 5, "comment": "Tokoku"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_input_invalid(self):
        response = self.client.post(self.product_url, {"rating": 9, "comment": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn("rating", response.json()["errors"])

    def test_target_tidak_ada_404(self):
        self.assertEqual(self.client.post(reverse("ulasan:create_product_review", args=[999]), {"rating": 5, "comment": "x"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("ulasan:create_store_review", args=["siapa"]), {"rating": 5, "comment": "x"}).status_code, 404)

    def test_post_only_dan_csrf(self):
        self.assertEqual(self.client.get(self.product_url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.login(username="buyer1", password=PASSWORD)
        self.assertEqual(client.post(self.product_url, {"rating": 5, "comment": "x"}).status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_anonim_ditolak(self):
        self.client.logout()
        response = self.client.post(self.product_url, {"rating": 5, "comment": "x"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("akun:login")))
        self.assertFalse(Review.objects.exists())


class EditDeleteReviewTests(ReviewTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.review = Review.objects.create(author=self.buyer, product=self.product, rating=3, comment="Lumayan")
        self.edit_url = reverse("ulasan:edit_review", args=[self.review.pk])
        self.delete_url = reverse("ulasan:delete_review", args=[self.review.pk])

    def test_edit_oleh_pemilik(self):
        self.client.login(username="buyer1", password=PASSWORD)
        data = self.client.post(self.edit_url, {"rating": 5, "comment": "Ternyata bagus"}).json()
        self.assertTrue(data["success"])
        self.assertEqual(data["review"]["rating"], 5)
        self.assertEqual(data["summary"]["average"], 5.0)
        self.review.refresh_from_db()
        self.assertEqual((self.review.rating, self.review.comment), (5, "Ternyata bagus"))

    def test_user_lain_403(self):
        self.client.login(username="buyer2", password=PASSWORD)
        response = self.client.post(self.edit_url, {"rating": 1, "comment": "Hack"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["success"])
        self.assertEqual(self.client.post(self.delete_url).status_code, 403)
        self.review.refresh_from_db()
        self.assertEqual(self.review.comment, "Lumayan")

    def test_hapus_oleh_pemilik(self):
        Review.objects.create(author=self.other, product=self.product, rating=5, comment="Oke")
        self.client.login(username="buyer1", password=PASSWORD)
        self.assertEqual(self.client.get(self.delete_url).status_code, 405)
        data = self.client.post(self.delete_url).json()
        self.assertTrue(data["success"])
        self.assertEqual(data["summary"], {"average": 5.0, "count": 1})
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_anonim_ditolak(self):
        self.assertEqual(self.client.post(self.edit_url, {"rating": 1, "comment": "x"}).status_code, 302)
        self.assertEqual(self.client.post(self.delete_url).status_code, 302)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())


class ListReviewTests(ReviewTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.r1 = Review.objects.create(author=self.buyer, product=self.product, rating=3, comment="Pertama")
        self.r2 = Review.objects.create(author=self.other, product=self.product, rating=5, comment="Kedua")
        self.r3 = Review.objects.create(author=self.buyer, seller=self.seller, rating=4, comment="Toko")

    def test_list_produk_sort_terbaru_dan_rating(self):
        url = reverse("ulasan:list_reviews")
        data = self.client.get(url, {"product": self.product.pk}).json()
        self.assertEqual([r["comment"] for r in data["reviews"]], ["Kedua", "Pertama"])
        self.assertEqual(data["summary"], {"average": 4.0, "count": 2})
        Review.objects.filter(pk=self.r1.pk).update(rating=5)
        Review.objects.filter(pk=self.r2.pk).update(rating=2)
        data = self.client.get(url, {"product": self.product.pk, "sort": "rating_tertinggi"}).json()
        self.assertEqual([r["rating"] for r in data["reviews"]], [5, 2])
        self.assertEqual(data["sort"], "rating_tertinggi")

    def test_list_toko_dan_is_owner(self):
        self.client.login(username="buyer1", password=PASSWORD)
        data = self.client.get(reverse("ulasan:list_reviews"), {"seller": "seller1"}).json()
        self.assertEqual(len(data["reviews"]), 1)
        self.assertTrue(data["reviews"][0]["is_owner"])
        self.assertIsNotNone(data["reviews"][0]["edit_url"])

    def test_list_butuh_target_dan_target_valid(self):
        self.assertEqual(self.client.get(reverse("ulasan:list_reviews")).status_code, 400)
        self.assertEqual(self.client.get(reverse("ulasan:list_reviews"), {"product": "abc"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("ulasan:list_reviews"), {"seller": "siapa"}).status_code, 404)

    def test_reviews_json_umum(self):
        data = self.client.get(reverse("ulasan:reviews_json")).json()
        self.assertTrue(data["success"])
        self.assertEqual(data["summary"]["count"], 3)
        self.assertFalse(any(r["is_owner"] for r in data["reviews"]))
        data = self.client.get(reverse("ulasan:reviews_json"), {"seller": "seller1"}).json()
        self.assertEqual([r["target"] for r in data["reviews"]], ["store"])


class ReviewSlotTests(ReviewTestMixin, TestCase):

    def render(self, template, context, user):
        request = RequestFactory().get("/listing/1/")
        request.user = user
        return render_to_string(template, {**context, "user": user}, request=request)

    def test_slot_produk_untuk_anonim(self):
        Review.objects.create(author=self.buyer, product=self.product, rating=4, comment="Bagus sekali")
        html = self.render("ulasan/slots/product_reviews.html", {"product": self.product}, AnonymousUser())
        self.assertIn("Bagus sekali", html)
        self.assertIn("4.0", html)
        self.assertIn("Masuk untuk menulis ulasan", html)
        self.assertIn(reverse("akun:login") + "?next=/listing/1/", html)
        self.assertNotIn("data-review-form", html)
        self.assertNotIn("data-review-edit", html)

    def test_slot_produk_untuk_pemilik_produk(self):
        html = self.render("ulasan/slots/product_reviews.html", {"product": self.product}, self.seller)
        self.assertIn("Ini produk milikmu", html)
        self.assertNotIn("data-review-form", html)

    def test_slot_form_tersembunyi_kalau_sudah_mengulas(self):
        html = self.render("ulasan/slots/product_reviews.html", {"product": self.product}, self.buyer)
        self.assertIn("data-review-form", html)
        self.assertNotIn("data-review-form hidden", html)
        Review.objects.create(author=self.buyer, product=self.product, rating=4, comment="Sudah")
        html = self.render("ulasan/slots/product_reviews.html", {"product": self.product}, self.buyer)
        self.assertIn("data-review-form hidden", html)
        self.assertIn("data-review-edit", html)

    def test_slot_toko(self):
        Review.objects.create(author=self.buyer, seller=self.seller, rating=5, comment="Seller ramah")
        Review.objects.create(author=self.other, seller=self.seller, rating=4, comment="Cepat")
        html = self.render("ulasan/slots/store_reviews.html", {"store_owner": self.seller}, self.other)
        self.assertIn("Ulasan Toko", html)
        self.assertIn("Seller ramah", html)
        self.assertIn("4.5", html)
        self.assertIn(reverse("ulasan:create_store_review", args=["seller1"]), html)
        html = self.render("ulasan/slots/store_reviews.html", {"store_owner": self.seller}, self.seller)
        self.assertIn("Ini tokomu", html)

    def test_slot_tanpa_target_kosong(self):
        html = self.render("ulasan/slots/store_reviews.html", {}, AnonymousUser())
        self.assertNotIn("data-reviews", html)


class SeedUlasanTests(TestCase):

    def test_seed_tanpa_buyer_keluar_rapi(self):
        out = StringIO()
        call_command("seed_ulasan", stdout=out)
        self.assertIn("seed_akun", out.getvalue())

    def test_seed_idempoten(self):
        seller1 = make_user("seller1", is_seller=True)
        make_user("seller2", is_seller=True)
        make_user("buyer1")
        make_product(seller1, "Linen blazer krem")
        call_command("seed_ulasan", stdout=StringIO())
        call_command("seed_ulasan", stdout=StringIO())
        self.assertEqual(Review.objects.filter(product__isnull=False).count(), 1)
        self.assertEqual(Review.objects.filter(seller__isnull=False).count(), 2)
