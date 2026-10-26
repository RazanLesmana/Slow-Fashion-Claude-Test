from django.urls import path
from . import views

app_name = "profil_toko"

urlpatterns = [
    path("buka/", views.buka_toko, name="buka_toko"),
    path("saya/", views.toko_saya, name="toko_saya"),
    path("size-chart/", views.size_chart_list, name="size_chart_list"),
    path("size-chart/json/", views.size_chart_json, name="size_chart_json"),
    path("size-chart/tambah/", views.size_chart_create, name="size_chart_create"),
    path("size-chart/<int:pk>/edit/", views.size_chart_edit, name="size_chart_edit"),
    path("size-chart/<int:pk>/hapus/", views.size_chart_delete, name="size_chart_delete"),
    path("<str:username>/", views.detail, name="detail"),
    path("<str:username>/produk/", views.store_products_json, name="store_products_json"),
    path("<str:username>/json/", views.store_json, name="store_json"),
    path("<str:username>/edit/", views.edit, name="edit"),
    path("<str:username>/tutup/", views.tutup_toko, name="tutup_toko"),
]
