from .services import cart_count as count_available


def cart_count(request):
    """Jumlah barang tersedia di keranjang untuk badge navbar (satu query, 0 untuk anonim)."""
    user = getattr(request, "user", None)
    return {"cart_count": count_available(user) if user is not None else 0}
