from urllib.parse import quote

from django import template
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from ulasan.forms import ReviewForm
from ulasan.models import Review
from ulasan.utils import SORT_OPTIONS, review_data, sorted_reviews, summary

register = template.Library()


def _assets_once(request):
    """CSS/JS ulasan cukup dimuat sekali per halaman."""
    if request is not None:
        if getattr(request, "_ulasan_assets_loaded", False):
            return ""
        request._ulasan_assets_loaded = True
    return format_html(
        '<link rel="stylesheet" href="{}"><script src="{}" defer></script>',
        static("ulasan/ulasan.css"),
        static("ulasan/ulasan.js"),
    )


def _block_context(context, kind, target):
    request = context.get("request")
    user = context.get("user")
    authenticated = bool(user and user.is_authenticated)

    if kind == "product":
        reviews = Review.objects.filter(product=target)
        is_target_owner = authenticated and target.seller_id == user.pk
        create_url = reverse("ulasan:create_product_review", args=[target.pk])
        list_query = f"product={target.pk}"
    else:
        reviews = Review.objects.filter(seller=target)
        is_target_owner = authenticated and target.pk == user.pk
        create_url = reverse("ulasan:create_store_review", args=[target.username])
        list_query = f"seller={target.username}"

    already_reviewed = authenticated and reviews.filter(author=user).exists()
    next_url = request.get_full_path() if request is not None else "/"
    return {
        "kind": kind,
        "title": "Ulasan Produk" if kind == "product" else "Ulasan Toko",
        "assets": _assets_once(request),
        "reviews": [review_data(r, user) for r in sorted_reviews(reviews)],
        "summary": summary(reviews),
        "sort_options": SORT_OPTIONS,
        "list_url": f"{reverse('ulasan:list_reviews')}?{list_query}",
        "create_url": create_url,
        "authenticated": authenticated,
        "is_target_owner": is_target_owner,
        "already_reviewed": already_reviewed,
        "form": ReviewForm(),
        "rating_values": [5, 4, 3, 2, 1],
        "login_url": f"{reverse('akun:login')}?next={quote(next_url)}",
        "csrf_token": context.get("csrf_token"),
    }


@register.inclusion_tag("ulasan/partials/reviews_block.html", takes_context=True)
def product_reviews(context, product):
    return _block_context(context, "product", product)


@register.inclusion_tag("ulasan/partials/reviews_block.html", takes_context=True)
def store_reviews(context, store_owner):
    return _block_context(context, "store", store_owner)


@register.filter
def stars(rating):
    """Rating (boleh desimal) -> daftar 5 nilai True/False untuk bintang penuh."""
    try:
        value = round(float(rating))
    except (TypeError, ValueError):
        value = 0
    return [i <= value for i in range(1, 6)]
