from django import template

from profil_toko.models import SizeChart, size_sort_key

register = template.Library()


@register.inclusion_tag("profil_toko/partials/size_chart_table.html")
def size_chart_for(product):
    """Tabel size chart untuk brand produk (case-insensitive), size produk di-highlight."""
    brand = (getattr(product, "brand", "") or "").strip()
    rows = []
    if brand:
        rows = sorted(
            SizeChart.objects.filter(brand__iexact=brand),
            key=lambda chart: size_sort_key(chart.size),
        )
    return {
        "brand": brand,
        "rows": rows,
        "selected_size": (getattr(product, "size", "") or "").strip().upper(),
    }
