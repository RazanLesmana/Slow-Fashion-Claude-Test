"""Filter dan sort katalog, dipakai halaman katalog dan endpoint JSON-nya."""
import re
from decimal import Decimal, InvalidOperation

from django.db.models import Q

from listing.models import Product
from listing.templatetags.format_tags import format_rupiah

SORT_OPTIONS = [
    ("terbaru", "Terbaru"),
    ("harga_terendah", "Harga terendah"),
    ("harga_tertinggi", "Harga tertinggi"),
]
SORT_ORDERING = {
    "terbaru": ["-created_at"],
    "harga_terendah": ["price", "-created_at"],
    "harga_tertinggi": ["-price", "-created_at"],
}
SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL"]
MULTI_KEYS = ("brand", "size", "condition")


def parse_price(value):
    """Angka harga dari query string; input invalid/negatif diabaikan (None)."""
    value = (value or "").strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", value):  # format ribuan: 85.000
        value = value.replace(".", "")
    # Hanya angka biasa (tanpa notasi ilmiah/NaN/negatif), maks. 12 digit seperti field harga.
    if not re.fullmatch(r"\d{1,12}(\.\d{1,2})?", value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _clean_list(values):
    seen, result = set(), []
    for value in values:
        value = value.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)
    return result


def size_sort_key(size):
    upper = size.upper()
    return (0, SIZE_ORDER.index(upper), upper) if upper in SIZE_ORDER else (1, 0, upper)


def filter_options():
    """Opsi brand dan size diambil dari produk publik yang ada di DB."""
    public = Product.objects.public()
    # Kalau ejaan brand berbeda huruf besar/kecil ("Zara" vs "zara"), pakai yang berhuruf kapital.
    raw_brands = sorted(set(public.exclude(brand="").values_list("brand", flat=True)), key=lambda b: (b.lower(), b.islower()))
    brands = _clean_list(raw_brands)
    sizes = sorted(_clean_list(public.values_list("size", flat=True)), key=size_sort_key)
    return {
        "brands": brands,
        "sizes": sizes,
        "conditions": Product.CONDITION_CHOICES,
        "categories": Product.CATEGORY_CHOICES,
        "sorts": SORT_OPTIONS,
    }


def parse_filters(params):
    """Ambil nilai filter yang valid dari QueryDict (request.GET)."""
    categories = dict(Product.CATEGORY_CHOICES)
    conditions = dict(Product.CONDITION_CHOICES)
    category = params.get("category", "")
    sort = params.get("sort", "terbaru")
    min_price = parse_price(params.get("min_price"))
    max_price = parse_price(params.get("max_price"))
    return {
        "q": params.get("q", "").strip(),
        "category": category if category in categories else "",
        "brand": _clean_list(params.getlist("brand")),
        "size": _clean_list(params.getlist("size")),
        "condition": [c for c in _clean_list(params.getlist("condition")) if c in conditions],
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort if sort in SORT_ORDERING else "terbaru",
    }


def _iexact_any(field, values):
    query = Q()
    for value in values:
        query |= Q(**{f"{field}__iexact": value})
    return query


def filter_products(filters):
    products = Product.objects.public().select_related("seller").prefetch_related("images")
    if filters["q"]:
        products = products.filter(Q(name__icontains=filters["q"]) | Q(brand__icontains=filters["q"]))
    if filters["category"]:
        products = products.filter(category=filters["category"])
    if filters["brand"]:
        products = products.filter(_iexact_any("brand", filters["brand"]))
    if filters["size"]:
        products = products.filter(_iexact_any("size", filters["size"]))
    if filters["condition"]:
        products = products.filter(condition__in=filters["condition"])
    if filters["min_price"] is not None:
        products = products.filter(price__gte=filters["min_price"])
    if filters["max_price"] is not None:
        products = products.filter(price__lte=filters["max_price"])
    return products.order_by(*SORT_ORDERING[filters["sort"]])


def active_filter_chips(params, filters):
    """Chip filter aktif, masing-masing dengan URL query untuk menghapus filter itu."""
    categories = dict(Product.CATEGORY_CHOICES)
    conditions = dict(Product.CONDITION_CHOICES)
    chips = []

    def without(key, value=None):
        query = params.copy()
        query.pop("page", None)
        if value is None:
            query.pop(key, None)
        else:
            query.setlist(key, [v for v in query.getlist(key) if v.strip().lower() != value.lower()])
        return "?" + query.urlencode()

    if filters["q"]:
        chips.append({"label": f"“{filters['q']}”", "url": without("q")})
    if filters["category"]:
        chips.append({"label": categories[filters["category"]], "url": without("category")})
    for key in MULTI_KEYS:
        for value in filters[key]:
            label = conditions.get(value, value) if key == "condition" else value
            chips.append({"label": label, "url": without(key, value)})
    if filters["min_price"] is not None:
        chips.append({"label": f"Min {format_rupiah(filters['min_price'])}", "url": without("min_price")})
    if filters["max_price"] is not None:
        chips.append({"label": f"Maks {format_rupiah(filters['max_price'])}", "url": without("max_price")})
    return chips


def query_without_page(params):
    query = params.copy()
    query.pop("page", None)
    return query.urlencode()
