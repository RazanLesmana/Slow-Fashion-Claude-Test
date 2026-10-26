from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from akun.models import Profile
from listing.models import Product
from listing.utils import product_card_data
from listing.views import seller_required
from .forms import SizeChartForm, StoreForm
from .models import SizeChart, Store, size_sort_key

# Tab produk di halaman toko -> status Product
STATUS_TABS = {
    "semua": None,
    "tersedia": "active",
    "terjual": "sold",
}


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def store_products(store, tab="semua"):
    products = (
        Product.objects.filter(seller=store.owner)
        .select_related("seller")
        .prefetch_related("images")
    )
    status = STATUS_TABS.get(tab)
    if status:
        products = products.filter(status=status)
    return products


def store_counts(store):
    counts = Product.objects.filter(seller=store.owner).aggregate(
        semua=Count("pk"),
        tersedia=Count("pk", filter=Q(status="active")),
        terjual=Count("pk", filter=Q(status="sold")),
    )
    return counts


def store_data(store, request):
    data = {
        "username": store.owner.username,
        "name": store.name,
        "initial": store.initial,
        "city": store.city,
        "description": store.description,
        "joined": store.created_at.isoformat(),
        "joined_display": store.created_at.strftime("%b %Y"),
        "url": reverse("profil_toko:detail", args=[store.owner.username]),
        "counts": store_counts(store),
    }
    # Nomor WhatsApp hanya untuk pengguna yang sudah masuk.
    if request.user.is_authenticated:
        data["whatsapp_number"] = store.whatsapp_number
        data["whatsapp_url"] = store.whatsapp_url
    return data


def get_owned_store(request, username):
    """Toko milik user yang login; toko orang lain -> 403."""
    store = get_object_or_404(Store.objects.select_related("owner"), owner__username=username)
    if store.owner_id != request.user.pk:
        return store, JsonResponse({
            "success": False,
            "message": "Kamu hanya bisa mengubah toko milikmu sendiri.",
        }, status=403)
    return store, None


# ---------- Store ----------

@login_required
def buka_toko(request):
    if hasattr(request.user, "store"):
        return redirect("profil_toko:toko_saya")

    if request.method == "POST":
        form = StoreForm(request.POST)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            store.save()

            profile = get_profile(request.user)
            profile.is_seller = True
            profile.save(update_fields=["is_seller"])

            messages.success(request, "Toko berhasil dibuka. Yuk tambah listing pertamamu!")
            return redirect("profil_toko:detail", username=request.user.username)
    else:
        form = StoreForm()

    return render(request, "profil_toko/buka_toko.html", {"form": form})


@login_required
def toko_saya(request):
    if hasattr(request.user, "store"):
        return redirect("profil_toko:detail", username=request.user.username)
    return redirect("profil_toko:buka_toko")


def detail(request, username):
    store = get_object_or_404(Store.objects.select_related("owner"), owner__username=username)
    is_owner = request.user.is_authenticated and store.owner_id == request.user.pk
    return render(request, "profil_toko/detail.html", {
        "store": store,
        "store_owner": store.owner,
        "products": store_products(store),
        "counts": store_counts(store),
        "is_owner": is_owner,
        "form": StoreForm(instance=store) if is_owner else None,
    })


@require_GET
def store_products_json(request, username):
    store = get_object_or_404(Store.objects.select_related("owner"), owner__username=username)
    tab = request.GET.get("status", "semua")
    if tab not in STATUS_TABS:
        tab = "semua"
    products = [product_card_data(p) for p in store_products(store, tab)]
    return JsonResponse({
        "success": True,
        "message": "OK",
        "status": tab,
        "counts": store_counts(store),
        "products": products,
    })


@require_GET
def store_json(request, username):
    store = get_object_or_404(Store.objects.select_related("owner"), owner__username=username)
    return JsonResponse({
        "success": True,
        "message": "OK",
        "store": store_data(store, request),
    })


@login_required
@require_POST
def edit(request, username):
    store, forbidden = get_owned_store(request, username)
    if forbidden:
        return forbidden

    form = StoreForm(request.POST, instance=store)
    if not form.is_valid():
        return JsonResponse({
            "success": False,
            "message": "Profil toko gagal disimpan. Periksa kembali isian.",
            "errors": form.errors.get_json_data(),
        }, status=400)

    form.save()
    return JsonResponse({
        "success": True,
        "message": "Profil toko berhasil diperbarui.",
        "store": store_data(store, request),
    })


@login_required
@require_POST
def tutup_toko(request, username):
    store, forbidden = get_owned_store(request, username)
    if forbidden:
        return forbidden

    # Produk tetap disimpan, tapi tidak tampil di katalog karena seller nonaktif.
    store.delete()
    profile = get_profile(request.user)
    profile.is_seller = False
    profile.save(update_fields=["is_seller"])

    return JsonResponse({
        "success": True,
        "message": "Toko sudah ditutup. Listing-mu disembunyikan dari katalog.",
        "redirect_url": reverse("akun:profil"),
    })


# ---------- Size chart ----------

def size_chart_queryset(brand=""):
    charts = SizeChart.objects.select_related("created_by")
    if brand:
        charts = charts.filter(brand__iexact=brand)
    return charts


def group_by_brand(charts):
    groups = {}
    for chart in charts:
        groups.setdefault(chart.brand.lower(), {"brand": chart.brand, "rows": []})["rows"].append(chart)
    result = sorted(groups.values(), key=lambda g: g["brand"].lower())
    for group in result:
        group["rows"].sort(key=lambda c: size_sort_key(c.size))
    return result


def size_chart_list(request):
    brand = request.GET.get("brand", "").strip()
    brands = sorted(
        {b.strip() for b in SizeChart.objects.values_list("brand", flat=True)},
        key=str.lower,
    )
    can_create = request.user.is_authenticated and get_profile(request.user).is_seller
    return render(request, "profil_toko/size_chart_list.html", {
        "groups": group_by_brand(size_chart_queryset(brand)),
        "brands": brands,
        "selected_brand": brand,
        "can_create": can_create,
    })


@seller_required
def size_chart_create(request):
    form = SizeChartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        chart = form.save(commit=False)
        chart.created_by = request.user
        chart.save()
        messages.success(request, f"Size chart {chart} berhasil ditambahkan.")
        return redirect(f"{reverse('profil_toko:size_chart_list')}?brand={chart.brand}")
    return render(request, "profil_toko/size_chart_form.html", {
        "form": form,
        "page_title": "Tambah Size Chart",
    })


@seller_required
def size_chart_edit(request, pk):
    chart = get_object_or_404(SizeChart, pk=pk)
    if not chart.can_manage(request.user):
        return HttpResponseForbidden("Kamu hanya bisa mengubah size chart yang kamu buat.")

    form = SizeChartForm(request.POST or None, instance=chart)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Size chart {chart} berhasil diperbarui.")
        return redirect(f"{reverse('profil_toko:size_chart_list')}?brand={chart.brand}")
    return render(request, "profil_toko/size_chart_form.html", {
        "form": form,
        "page_title": "Edit Size Chart",
        "chart": chart,
    })


@seller_required
@require_POST
def size_chart_delete(request, pk):
    chart = get_object_or_404(SizeChart, pk=pk)
    if not chart.can_manage(request.user):
        return JsonResponse({
            "success": False,
            "message": "Kamu hanya bisa menghapus size chart yang kamu buat.",
        }, status=403)
    label = str(chart)
    chart.delete()
    return JsonResponse({
        "success": True,
        "message": f"Size chart {label} dihapus.",
    })


@require_GET
def size_chart_json(request):
    brand = request.GET.get("brand", "").strip()
    charts = sorted(
        size_chart_queryset(brand),
        key=lambda c: (c.brand.lower(), size_sort_key(c.size)),
    )
    return JsonResponse({
        "success": True,
        "message": "OK",
        "brand": brand,
        "count": len(charts),
        "size_charts": [chart.to_dict() for chart in charts],
    })
