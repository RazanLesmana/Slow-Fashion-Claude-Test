from django.urls import path
from . import views

app_name = "listing"

urlpatterns = [
    path("", views.my_listings, name="my_listings"),
    path("tambah/", views.product_create, name="product_create"),
    path("<int:pk>/", views.product_detail, name="product_detail"),
    path("<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("<int:pk>/hapus/", views.product_delete, name="product_delete"),
    path("<int:pk>/terjual/", views.product_mark_sold, name="product_mark_sold"),
]