from django.urls import path
from . import views

app_name = "pesanan"

urlpatterns = [
    path("keranjang/", views.keranjang, name="keranjang"),
    path("keranjang/json/", views.cart_json, name="cart_json"),
    path("keranjang/tambah/<int:product_id>/", views.cart_add, name="cart_add"),
    path("keranjang/hapus/<int:item_id>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/berhasil/<uuid:checkout_ref>/", views.checkout_success, name="checkout_success"),
    path("pesanan/", views.pesanan_saya, name="pesanan_saya"),
    path("pesanan/masuk/", views.pesanan_masuk, name="pesanan_masuk"),
    path("pesanan/json/", views.orders_json, name="orders_json"),
    path("pesanan/<str:code>/", views.order_detail, name="order_detail"),
    path("pesanan/<str:code>/kirim/", views.order_ship, name="order_ship"),
    path("pesanan/<str:code>/selesai/", views.order_complete, name="order_complete"),
    path("pesanan/<str:code>/batal/", views.order_cancel, name="order_cancel"),
]
