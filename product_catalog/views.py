from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from listing.models import Product
from listing.utils import product_card_data
from .filters import (
    active_filter_chips, filter_options, filter_products, parse_filters, query_without_page,
)
from .forms import WishlistNoteForm
from .models import WishlistItem

PER_PAGE = 12


def paginate(request, queryset):
    return Paginator(queryset, PER_PAGE).get_page(request.GET.get("page"))


# ---------- Katalog ----------

def katalog(request):
    filters = parse_filters(request.GET)
    page_obj = paginate(request, filter_products(filters))
    chips = active_filter_chips(request.GET, filters)
    sort = request.GET.get("sort")
    return render(request, "product_catalog/katalog.html", {
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "filters": filters,
        "options": filter_options(),
        "active_chips": chips,
        # Filter di sidebar (tidak termasuk pencarian & kategori) untuk tombol "Filter (n)" di mobile.
        "sidebar_count": len(filters["brand"]) + len(filters["size"]) + len(filters["condition"])
        + (filters["min_price"] is not None) + (filters["max_price"] is not None),
        "querystring": query_without_page(request.GET),
        "clear_url": f"?sort={sort}" if sort else "?",
    })


@require_GET
def katalog_json(request):
    filters = parse_filters(request.GET)
    page_obj = paginate(request, filter_products(filters))
    return JsonResponse({
        "success": True,
        "message": "OK",
        "count": page_obj.paginator.count,
        "page": page_obj.number,
        "num_pages": page_obj.paginator.num_pages,
        "filters": {
            **filters,
            "min_price": int(filters["min_price"]) if filters["min_price"] is not None else None,
            "max_price": int(filters["max_price"]) if filters["max_price"] is not None else None,
        },
        "products": [product_card_data(p) for p in page_obj.object_list],
    })


# ---------- Wishlist ----------

def wishlist_count(user):
    return WishlistItem.objects.filter(user=user).count()


def item_data(item):
    return {
        "id": item.pk,
        "note": item.note,
        "created_at": item.created_at.isoformat(),
        "product": product_card_data(item.product),
    }


@login_required
def wishlist(request):
    items = (
        WishlistItem.objects.filter(user=request.user)
        .select_related("product", "product__seller")
        .prefetch_related("product__images")
    )
    total = items.count()
    category = request.GET.get("category", "")
    if category in dict(Product.CATEGORY_CHOICES):
        items = items.filter(product__category=category)
    else:
        category = ""
    return render(request, "product_catalog/wishlist.html", {
        "items": items,
        "total": total,
        "selected_category": category,
        "categories": Product.CATEGORY_CHOICES,
    })


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    item = WishlistItem.objects.filter(user=request.user, product=product).first()
    if item:
        item.delete()
        in_wishlist = False
        message = "Dihapus dari wishlist."
    else:
        WishlistItem.objects.create(user=request.user, product=product)
        in_wishlist = True
        message = "Ditambahkan ke wishlist."
    return JsonResponse({
        "success": True,
        "message": message,
        "in_wishlist": in_wishlist,
        "product_id": product.pk,
        "count": wishlist_count(request.user),
    })


@login_required
@require_POST
def update_note(request, item_id):
    item = get_object_or_404(WishlistItem, pk=item_id, user=request.user)
    form = WishlistNoteForm(request.POST, instance=item)
    if not form.is_valid():
        return JsonResponse({
            "success": False,
            "message": "Catatan gagal disimpan.",
            "errors": form.errors.get_json_data(),
        }, status=400)
    form.save()
    return JsonResponse({
        "success": True,
        "message": "Catatan disimpan.",
        "note": item.note,
    })


@login_required
@require_POST
def remove_item(request, item_id):
    item = get_object_or_404(WishlistItem, pk=item_id, user=request.user)
    item.delete()
    return JsonResponse({
        "success": True,
        "message": "Dihapus dari wishlist.",
        "count": wishlist_count(request.user),
    })


@login_required
@require_GET
def wishlist_json(request):
    items = (
        WishlistItem.objects.filter(user=request.user)
        .select_related("product", "product__seller")
        .prefetch_related("product__images")
    )
    return JsonResponse({
        "success": True,
        "message": "OK",
        "count": len(items),
        "items": [item_data(item) for item in items],
    })
