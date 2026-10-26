from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from akun.models import Profile
from .forms import ProductForm, ProductImageFormSet
from .models import Product
from .utils import product_card_data


def seller_required(view_func):
    """
    Allow access only to logged-in users whose Profile
    has is_seller=True.
    """
    @wraps(view_func)
    @login_required(login_url="akun:login")
    def wrapper(request, *args, **kwargs):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return HttpResponseForbidden(
                "Kamu harus memiliki profil seller untuk mengakses halaman ini."
            )

        if not profile.is_seller:
            return HttpResponseForbidden(
                "Halaman ini hanya bisa diakses oleh seller."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def get_own_product(request, pk):
    """Produk milik seller yang login; produk orang lain -> 404."""
    return get_object_or_404(Product, pk=pk, seller=request.user)


def status_counts(seller):
    counts = Product.objects.filter(seller=seller).aggregate(
        semua=Count("pk"),
        active=Count("pk", filter=Q(status="active")),
        sold=Count("pk", filter=Q(status="sold")),
    )
    return counts


def product_detail_data(product):
    data = product_card_data(product)
    data.update({
        "description": product.description,
        "images": [
            {"url": image.image.url, "alt_text": image.alt_text}
            for image in product.images.all()
        ],
        "store_url": reverse("profil_toko:detail", args=[product.seller.username]),
        "updated_at": product.updated_at.isoformat(),
    })
    return data


@seller_required
def product_create(request):
    """
    Display the Add Product form and save a new listing.
    """
    product = Product(seller=request.user)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        image_formset = ProductImageFormSet(
            request.POST,
            request.FILES,
            instance=product,
        )

        if form.is_valid() and image_formset.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()

            image_formset.instance = product
            image_formset.save()

            messages.success(request, "Produk berhasil ditambahkan!")
            return redirect("listing:my_listings")
    else:
        form = ProductForm(instance=product)
        image_formset = ProductImageFormSet(instance=product)

    return render(
        request,
        "listing/product_form.html",
        {
            "form": form,
            "image_formset": image_formset,
            "page_title": "Tambah Listing",
        },
    )


@seller_required
def my_listings(request):
    """
    Show only the current seller's products.
    Supports filtering by status and category.
    """
    products = (
        Product.objects.filter(seller=request.user)
        .prefetch_related("images")
    )

    selected_status = request.GET.get("status", "")
    selected_category = request.GET.get("category", "")

    valid_statuses = dict(Product.STATUS_CHOICES)
    valid_categories = dict(Product.CATEGORY_CHOICES)

    if selected_status not in valid_statuses:
        selected_status = ""
    if selected_category not in valid_categories:
        selected_category = ""

    if selected_status:
        products = products.filter(status=selected_status)

    if selected_category:
        products = products.filter(category=selected_category)

    return render(
        request,
        "listing/my_listings.html",
        {
            "products": products,
            "counts": status_counts(request.user),
            "status_choices": Product.STATUS_CHOICES,
            "category_choices": Product.CATEGORY_CHOICES,
            "selected_status": selected_status,
            "selected_category": selected_category,
        },
    )


def product_detail(request, pk):
    """
    Public product page. Edit/delete/mark sold buttons are only
    rendered for the seller who owns the product.
    """
    product = get_object_or_404(
        Product.objects.select_related("seller").prefetch_related("images"),
        pk=pk,
    )
    is_owner = request.user.is_authenticated and product.seller_id == request.user.pk

    same_store = (
        Product.objects.public()
        .filter(seller=product.seller)
        .exclude(pk=product.pk)
        .prefetch_related("images")[:4]
    )

    return render(
        request,
        "listing/product_detail.html",
        {
            "product": product,
            "is_owner": is_owner,
            "same_store": same_store,
        },
    )


@seller_required
def product_edit(request, pk):
    """
    Edit a product owned by the logged-in seller.
    """
    product = get_own_product(request, pk)

    if request.method == "POST":
        form = ProductForm(
            request.POST,
            instance=product,
        )

        image_formset = ProductImageFormSet(
            request.POST,
            request.FILES,
            instance=product,
        )

        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()

            messages.success(
                request,
                "Produk berhasil diperbarui!",
            )

            return redirect(
                "listing:product_detail",
                pk=product.pk,
            )

    else:
        form = ProductForm(instance=product)

        image_formset = ProductImageFormSet(
            instance=product,
        )

    return render(
        request,
        "listing/product_form.html",
        {
            "form": form,
            "image_formset": image_formset,
            "page_title": "Edit Listing",
            "product": product,
        },
    )


@seller_required
@require_POST
def product_delete(request, pk):
    product = get_own_product(request, pk)

    product.delete()

    return JsonResponse({
        "success": True,
        "message": "Produk berhasil dihapus.",
        "counts": status_counts(request.user),
        "redirect_url": reverse("listing:my_listings"),
    })


def _set_status(request, pk, new_status, already_message, success_message):
    product = get_own_product(request, pk)

    if product.status == new_status:
        return JsonResponse({
            "success": False,
            "message": already_message,
        }, status=400)

    product.status = new_status
    product.save(update_fields=["status", "updated_at"])

    return JsonResponse({
        "success": True,
        "message": success_message,
        "status": product.status,
        "status_display": product.get_status_display(),
        "counts": status_counts(request.user),
    })


@seller_required
@require_POST
def product_mark_sold(request, pk):
    return _set_status(
        request, pk, "sold",
        "Produk ini sudah ditandai sebagai terjual.",
        "Produk berhasil ditandai sebagai terjual.",
    )


@seller_required
@require_POST
def product_mark_active(request, pk):
    return _set_status(
        request, pk, "active",
        "Produk ini masih aktif.",
        "Produk kembali aktif dan tampil di katalog.",
    )


@require_GET
def product_list_json(request):
    """Produk aktif publik (seller aktif). Filter opsional: category, seller."""
    products = (
        Product.objects.public()
        .select_related("seller")
        .prefetch_related("images")
    )
    category = request.GET.get("category")
    if category in dict(Product.CATEGORY_CHOICES):
        products = products.filter(category=category)
    seller = request.GET.get("seller")
    if seller:
        products = products.filter(seller__username=seller)

    data = [product_card_data(product) for product in products]
    return JsonResponse({
        "success": True,
        "message": "OK",
        "count": len(data),
        "products": data,
    })


@require_GET
def product_detail_json(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("seller").prefetch_related("images"),
        pk=pk,
    )
    return JsonResponse({
        "success": True,
        "message": "OK",
        "product": product_detail_data(product),
    })


@seller_required
@require_GET
def my_products_json(request):
    products = (
        Product.objects.filter(seller=request.user)
        .select_related("seller")
        .prefetch_related("images")
    )
    status = request.GET.get("status")
    if status in dict(Product.STATUS_CHOICES):
        products = products.filter(status=status)
    category = request.GET.get("category")
    if category in dict(Product.CATEGORY_CHOICES):
        products = products.filter(category=category)

    data = [product_card_data(product) for product in products]
    return JsonResponse({
        "success": True,
        "message": "OK",
        "count": len(data),
        "counts": status_counts(request.user),
        "products": data,
    })
