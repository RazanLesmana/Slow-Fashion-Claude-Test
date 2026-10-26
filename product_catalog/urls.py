from django.urls import path
from . import views

app_name = "product_catalog"

urlpatterns = [
    path("katalog/", views.katalog, name="katalog"),
    path("katalog/json/", views.katalog_json, name="katalog_json"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/json/", views.wishlist_json, name="wishlist_json"),
    path("wishlist/toggle/<int:product_id>/", views.toggle_wishlist, name="toggle_wishlist"),
    path("wishlist/<int:item_id>/catatan/", views.update_note, name="update_note"),
    path("wishlist/<int:item_id>/hapus/", views.remove_item, name="remove_item"),
]
