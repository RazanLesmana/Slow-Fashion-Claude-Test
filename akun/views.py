from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from .forms import RegisterForm, ProfileForm
from .models import Profile
from listing.models import Product

LANDING_CATEGORIES = ["atasan", "bawahan", "outerwear", "dress"]

def user_has_store(user):
    # Model Store ada di app profil_toko (related_name="store"). hasattr aman
    # dipakai walau app itu belum lengkap: RelatedObjectDoesNotExist adalah
    # turunan AttributeError, dan atribut yang belum ada juga AttributeError.
    return user.is_authenticated and hasattr(user, "store")

def seller_cta_url(user):
    """Tujuan tombol "Jadi Seller": buka toko kalau sudah seller tapi belum punya toko."""
    if user.is_authenticated and Profile.for_user(user).is_seller and not user_has_store(user):
        return reverse("profil_toko:buka_toko")
    return reverse("akun:profil")

def landing(request):
    products = (
        Product.objects.public()
        .select_related("seller")
        .prefetch_related("images")[:8]
    )
    categories = [
        (value, label) for value, label in Product.CATEGORY_CHOICES
        if value in LANDING_CATEGORIES
    ]
    return render(request, "landing.html", {
        "products": products,
        "categories": categories,
        "seller_cta_url": seller_cta_url(request.user),
    })

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Profile dibuat otomatis oleh signal post_save (akun/signals.py).
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Akun berhasil dibuat. Selamat datang di LaPAKAIAN!")
            return redirect("akun:profil")
    else:
        form = RegisterForm()
    return render(request, "akun/register.html", {"form": form})

def _safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""

def login_view(request):
    next_url = _safe_next_url(request)
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            return redirect(next_url or "landing")
    else:
        form = AuthenticationForm()
    return render(request, "akun/login.html", {"form": form, "next": next_url})

@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("landing")

@login_required
def profil(request):
    profile = Profile.for_user(request.user)
    return render(request, "akun/profil.html", {
        "profile": profile,
        "form": ProfileForm(instance=profile),
        "has_store": user_has_store(request.user),
    })

@login_required
@require_POST
def edit_profil(request):
    profile = Profile.for_user(request.user)
    form = ProfileForm(request.POST, instance=profile)
    if not form.is_valid():
        return JsonResponse({
            "success": False,
            "message": "Bio gagal disimpan.",
            "errors": form.errors.get_json_data(),
        }, status=400)
    form.save()
    return JsonResponse({
        "success": True,
        "message": "Bio berhasil disimpan.",
        "bio": profile.bio,
    })

@login_required
@require_POST
def hapus_akun(request):
    user = request.user
    auth_logout(request)
    user.delete()
    return JsonResponse({
        "success": True,
        "message": "Akun kamu sudah dihapus.",
        "redirect_url": reverse("landing"),
    })

@login_required
@require_POST
def toggle_seller(request):
    profile = Profile.for_user(request.user)
    profile.is_seller = not profile.is_seller
    profile.save(update_fields=["is_seller"])

    data = {
        "success": True,
        "is_seller": profile.is_seller,
        "status_display": "Seller" if profile.is_seller else "Buyer",
    }
    if profile.is_seller:
        data["message"] = "Mode seller aktif."
        if not user_has_store(request.user):
            data["message"] = "Mode seller aktif. Lengkapi profil tokomu dulu, ya."
            data["redirect_url"] = reverse("profil_toko:buka_toko")
    else:
        data["message"] = "Mode seller dinonaktifkan."
    return JsonResponse(data)

@login_required
@require_GET
def profil_json(request):
    user = request.user
    profile = Profile.for_user(user)
    return JsonResponse({
        "success": True,
        "message": "OK",
        "profile": {
            "username": user.username,
            "bio": profile.bio,
            "is_seller": profile.is_seller,
            "has_store": user_has_store(user),
            "date_joined": user.date_joined.isoformat(),
            "product_count": user.product_listings.count(),
            "profile_url": reverse("akun:profil"),
        },
    })
