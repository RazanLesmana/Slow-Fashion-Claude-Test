from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

from listing.models import Product

register = template.Library()


def format_rupiah(value):
    """Ubah angka menjadi format Rp85.000 (tanpa desimal, titik ribuan)."""
    if value is None or value == "":
        return ""
    try:
        amount = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return value
    sign = "-" if amount < 0 else ""
    return f"{sign}Rp{abs(int(amount)):,}".replace(",", ".")


@register.filter
def rupiah(value):
    return format_rupiah(value)


@register.simple_tag
def product_categories():
    """Daftar (value, label) kategori produk, dipakai di navbar dan footer."""
    return Product.CATEGORY_CHOICES
