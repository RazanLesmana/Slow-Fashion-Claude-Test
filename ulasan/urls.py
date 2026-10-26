from django.urls import path
from . import views

app_name = "ulasan"

urlpatterns = [
    path("produk/<int:product_id>/", views.create_product_review, name="create_product_review"),
    path("toko/<str:username>/", views.create_store_review, name="create_store_review"),
    path("list/", views.list_reviews, name="list_reviews"),
    path("json/", views.reviews_json, name="reviews_json"),
    path("<int:pk>/edit/", views.edit_review, name="edit_review"),
    path("<int:pk>/hapus/", views.delete_review, name="delete_review"),
]
