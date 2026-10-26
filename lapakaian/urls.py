"""
URL configuration for lapakaian project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from akun import views as akun_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", akun_views.landing, name="landing"),
    path("akun/", include("akun.urls")),
    path("listing/", include("listing.urls")),
    path("toko/", include("profil_toko.urls")),
    # product_catalog mengatur path katalog/ dan wishlist/ di dalam app-nya
    path("", include("product_catalog.urls")),
    path("ulasan/", include("ulasan.urls")),
    # pesanan mengatur path keranjang/, checkout/, dan pesanan/ di dalam app-nya
    path("", include("pesanan.urls")),
]

handler404 = "lapakaian.views.page_not_found"

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
