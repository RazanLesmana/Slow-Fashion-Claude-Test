from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from listing.models import Product
from .forms import ReviewForm
from .models import Review
from .utils import parse_sort, review_data, reviews_for_params, sorted_reviews, summary


def form_error_response(form, message="Ulasan gagal disimpan."):
    errors = form.errors.get_json_data()
    non_field = [e["message"] for e in errors.get("__all__", [])]
    return JsonResponse({
        "success": False,
        "message": non_field[0] if non_field else message,
        "errors": errors,
    }, status=400)


def _create(request, **target):
    form = ReviewForm(request.POST, author=request.user, **target)
    if not form.is_valid():
        return form_error_response(form)
    review = form.save()
    target_reviews = Review.objects.filter(**target)
    return JsonResponse({
        "success": True,
        "message": "Ulasan berhasil dikirim. Terima kasih!",
        "review": review_data(review, request.user),
        "summary": summary(target_reviews),
    }, status=201)


@login_required
@require_POST
def create_product_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    return _create(request, product=product)


@login_required
@require_POST
def create_store_review(request, username):
    seller = get_object_or_404(User, username=username)
    return _create(request, seller=seller)


def _own_review_or_403(request, pk):
    review = get_object_or_404(Review.objects.select_related("author"), pk=pk)
    if review.author_id != request.user.pk:
        return review, JsonResponse({
            "success": False,
            "message": "Kamu hanya bisa mengubah ulasanmu sendiri.",
        }, status=403)
    return review, None


def _target_summary(review):
    if review.product_id:
        return summary(Review.objects.filter(product_id=review.product_id))
    return summary(Review.objects.filter(seller_id=review.seller_id))


@login_required
@require_POST
def edit_review(request, pk):
    review, forbidden = _own_review_or_403(request, pk)
    if forbidden:
        return forbidden
    form = ReviewForm(request.POST, instance=review, author=request.user)
    if not form.is_valid():
        return form_error_response(form)
    review = form.save()
    return JsonResponse({
        "success": True,
        "message": "Ulasan diperbarui.",
        "review": review_data(review, request.user),
        "summary": _target_summary(review),
    })


@login_required
@require_POST
def delete_review(request, pk):
    review, forbidden = _own_review_or_403(request, pk)
    if forbidden:
        return forbidden
    target_summary_source = Review(product_id=review.product_id, seller_id=review.seller_id)
    review.delete()
    return JsonResponse({
        "success": True,
        "message": "Ulasan dihapus.",
        "summary": _target_summary(target_summary_source),
    })


def _list_response(request, require_target):
    if require_target and not (request.GET.get("product") or request.GET.get("seller")):
        return JsonResponse({
            "success": False,
            "message": "Sertakan parameter product=<id> atau seller=<username>.",
        }, status=400)
    reviews, error = reviews_for_params(request.GET)
    if error:
        return JsonResponse({"success": False, "message": error}, status=404)
    sort = parse_sort(request.GET.get("sort"))
    return JsonResponse({
        "success": True,
        "message": "OK",
        "sort": sort,
        "summary": summary(reviews),
        "reviews": [review_data(r, request.user) for r in sorted_reviews(reviews, sort)],
    })


@require_GET
def list_reviews(request):
    """Daftar ulasan satu produk/toko untuk UI (ganti sort tanpa reload)."""
    return _list_response(request, require_target=True)


@require_GET
def reviews_json(request):
    """Endpoint JSON umum: semua ulasan, bisa difilter product/seller dan di-sort."""
    return _list_response(request, require_target=False)
