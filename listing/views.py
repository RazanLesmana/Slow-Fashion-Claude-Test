from django.shortcuts import render

# Create your views here.
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from akun.models import Profile
from .models import Product
from .forms import ProductForm, ProductImageFormSet

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST



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
            "page_title": "Tambah Produk",
        },
    )


@seller_required
def my_listings(request):
    """
    Show only the current seller's products.
    Supports filtering by status and category.
    """
    products = Product.objects.filter(seller=request.user)

    selected_status = request.GET.get("status", "")
    selected_category = request.GET.get("category", "")

    valid_statuses = dict(Product.STATUS_CHOICES)
    valid_categories = dict(Product.CATEGORY_CHOICES)

    if selected_status in valid_statuses:
        products = products.filter(status=selected_status)

    if selected_category in valid_categories:
        products = products.filter(category=selected_category)

    return render(
        request,
        "listing/my_listings.html",
        {
            "products": products,
            "status_choices": Product.STATUS_CHOICES,
            "category_choices": Product.CATEGORY_CHOICES,
            "selected_status": selected_status,
            "selected_category": selected_category,
        },
    )

@seller_required
def product_detail(request, pk):
    """
    Display the details of a product owned by the seller.
    """
    product = get_object_or_404(
        Product,
        pk=pk,
        seller=request.user,
    )

    return render(
        request,
        "listing/product_detail.html",
        {
            "product": product,
        },
    )

@seller_required
def product_edit(request, pk):
    """
    Edit a product owned by the logged-in seller.
    """
    product = get_object_or_404(
        Product,
        pk=pk,
        seller=request.user,
    )

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
            "page_title": "Edit Produk",
            "product": product,
        },
    )

@seller_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(
        Product,
        pk=pk,
        seller=request.user
    )

    product.delete()

    return JsonResponse({
        "success": True,
        "message": "Produk berhasil dihapus."
    })


@seller_required
@require_POST
def product_mark_sold(request, pk):
    product = get_object_or_404(
        Product,
        pk=pk,
        seller=request.user
    )

    if product.status == "sold":
        return JsonResponse({
            "success": False,
            "message": "Produk ini sudah ditandai sebagai terjual."
        }, status=400)

    product.status = "sold"
    product.save(update_fields=["status", "updated_at"])

    return JsonResponse({
        "success": True,
        "message": "Produk berhasil ditandai sebagai terjual.",
        "status": product.status,
        "status_display": product.get_status_display()
    })