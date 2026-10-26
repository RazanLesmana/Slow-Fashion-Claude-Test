from django.urls import reverse

from listing.templatetags.format_tags import format_rupiah


def first_image_url(product):
    # .all() memakai hasil prefetch_related("images") kalau ada (maks. 5 foto).
    images = product.images.all()
    return images[0].image.url if images else ""


def product_card_data(product):
    """
    Data satu produk dalam bentuk dict, dengan struktur yang sama
    dengan templates/partials/product_card.html. Dipakai endpoint JSON
    lintas modul dan oleh renderProductCard() di static/js/utils.js.
    """
    return {
        "id": product.pk,
        "name": product.name,
        "brand": product.brand,
        "size": product.size,
        "category": product.category,
        "category_display": product.get_category_display(),
        "condition": product.condition,
        "condition_display": product.get_condition_display(),
        "price": int(product.price),
        "price_display": format_rupiah(product.price),
        "status": product.status,
        "status_display": product.get_status_display(),
        "image_url": first_image_url(product),
        "detail_url": reverse("listing:product_detail", args=[product.pk]),
        "seller": product.seller.username,
        "created_at": product.created_at.isoformat(),
    }
