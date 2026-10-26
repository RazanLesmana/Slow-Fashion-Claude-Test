import json

from django import template
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from product_catalog.models import WishlistItem

register = template.Library()


def wishlist_ids(request):
    """Set product_id di wishlist user, diambil sekali per request."""
    if request is None or not request.user.is_authenticated:
        return set()
    if not hasattr(request, "_wishlist_product_ids"):
        request._wishlist_product_ids = set(
            WishlistItem.objects.filter(user=request.user).values_list("product_id", flat=True)
        )
    return request._wishlist_product_ids


def _once(request, key):
    """True hanya pada pemanggilan pertama per request (aset tidak dimuat dobel)."""
    if request is None:
        return True
    if getattr(request, key, False):
        return False
    setattr(request, key, True)
    return True


@register.inclusion_tag("product_catalog/partials/wishlist_button.html", takes_context=True)
def wishlist_button(context, product):
    request = context.get("request")
    user = context.get("user")
    return {
        "product": product,
        "request": request,
        "is_authenticated": bool(user and user.is_authenticated),
        "in_wishlist": product.pk in wishlist_ids(request),
    }


@register.simple_tag(takes_context=True)
def wishlist_css(context):
    if not _once(context.get("request"), "_wishlist_css_loaded"):
        return ""
    return format_html('<link rel="stylesheet" href="{}">', static("product_catalog/product_catalog.css"))


@register.simple_tag(takes_context=True)
def wishlist_js(context):
    request = context.get("request")
    if not _once(request, "_wishlist_js_loaded"):
        return ""
    # Data untuk kartu yang dibangun JS (renderProductCard): state awal + URL toggle.
    data = json.dumps({
        "ids": sorted(wishlist_ids(request)),
        "toggle_url": reverse("product_catalog:toggle_wishlist", args=[0]),
    }).replace("<", "\\u003c")
    return format_html(
        '<script type="application/json" id="wishlist-data">{}</script>'
        '<script src="{}" defer></script>',
        mark_safe(data),
        static("product_catalog/product_catalog.js"),
    )
