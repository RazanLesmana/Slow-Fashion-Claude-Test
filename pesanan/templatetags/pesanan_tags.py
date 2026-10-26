from urllib.parse import quote

from django import template
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from pesanan.models import CartItem
from pesanan.services import tanggal as format_tanggal, unavailable_reason

register = template.Library()


def cart_product_ids(request):
    """Set product_id di keranjang user, diambil sekali per request."""
    if request is None or not request.user.is_authenticated:
        return set()
    if not hasattr(request, "_cart_product_ids"):
        request._cart_product_ids = set(
            CartItem.objects.filter(user=request.user).values_list("product_id", flat=True)
        )
    return request._cart_product_ids


@register.simple_tag(takes_context=True)
def pesanan_assets(context):
    """CSS/JS modul pesanan, dimuat sekali per halaman (slot bisa muncul di halaman modul lain)."""
    request = context.get("request")
    if request is not None:
        if getattr(request, "_pesanan_assets_loaded", False):
            return ""
        request._pesanan_assets_loaded = True
    return format_html(
        '<link rel="stylesheet" href="{}"><script src="{}" defer></script>',
        static("pesanan/pesanan.css"),
        static("pesanan/pesanan.js"),
    )


@register.inclusion_tag("pesanan/partials/add_to_cart.html", takes_context=True)
def cart_button(context, product, compact=False):
    request = context.get("request")
    user = context.get("user")
    authenticated = bool(user and user.is_authenticated)
    if not authenticated:
        state = "anonymous"
    elif product.seller_id == user.pk:
        state = "owner"
    elif product.status != "active":
        state = "sold"
    elif unavailable_reason(product, user):
        state = "inactive"
    elif product.pk in cart_product_ids(request):
        state = "in_cart"
    else:
        state = "available"
    next_url = request.get_full_path() if request is not None else "/"
    return {
        "product": product,
        "state": state,
        "compact": compact,
        "request": request,
        "login_url": f"{reverse('akun:login')}?next={quote(next_url)}",
    }


@register.filter
def tanggal(value, with_time=False):
    return format_tanggal(value, with_time=bool(with_time))
