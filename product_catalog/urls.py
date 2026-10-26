from django.urls import path
from . import views

app_name = "product_catalog"

urlpatterns = [
    path("katalog/", views.katalog, name="katalog"),
    path("wishlist/", views.wishlist, name="wishlist"),
]
