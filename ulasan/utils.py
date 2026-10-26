from django.contrib.auth.models import User
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format

from listing.models import Product
from .models import Review

SORT_OPTIONS = [
    ("terbaru", "Terbaru"),
    ("rating_tertinggi", "Rating tertinggi"),
]
SORT_ORDERING = {
    "terbaru": ["-created_at"],
    "rating_tertinggi": ["-rating", "-created_at"],
}


def parse_sort(value):
    return value if value in SORT_ORDERING else "terbaru"


def sorted_reviews(queryset, sort="terbaru"):
    return queryset.select_related("author").order_by(*SORT_ORDERING[parse_sort(sort)])


def summary(queryset):
    data = queryset.aggregate(average=Avg("rating"), count=Count("pk"))
    average = round(data["average"], 1) if data["average"] is not None else 0
    return {"average": average, "count": data["count"]}


def review_data(review, user=None):
    is_owner = bool(user and user.is_authenticated and review.author_id == user.pk)
    created = timezone.localtime(review.created_at)
    return {
        "id": review.pk,
        "author": review.author.username,
        "rating": review.rating,
        "comment": review.comment,
        "target": "product" if review.product_id else "store",
        "product_id": review.product_id,
        "seller": review.seller.username if review.seller_id else None,
        "created_at": review.created_at.isoformat(),
        "created_display": date_format(created, "j M Y"),
        "edited": (review.updated_at - review.created_at).total_seconds() > 1,
        "is_owner": is_owner,
        "edit_url": reverse("ulasan:edit_review", args=[review.pk]) if is_owner else None,
        "delete_url": reverse("ulasan:delete_review", args=[review.pk]) if is_owner else None,
    }


def reviews_for_params(params):
    """
    Queryset ulasan sesuai filter GET: product=<id> atau seller=<username>.
    Mengembalikan (queryset, error) — error berisi pesan kalau parameter tidak valid.
    """
    reviews = Review.objects.all()
    product_id = params.get("product")
    username = params.get("seller")
    if product_id:
        if not product_id.isdigit() or not Product.objects.filter(pk=product_id).exists():
            return None, "Produk tidak ditemukan."
        reviews = reviews.filter(product_id=product_id)
    if username:
        if not User.objects.filter(username=username).exists():
            return None, "Toko tidak ditemukan."
        reviews = reviews.filter(seller__username=username)
    return reviews, None
