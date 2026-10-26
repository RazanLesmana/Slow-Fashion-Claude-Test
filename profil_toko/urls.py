from django.urls import path
from . import views

app_name = "profil_toko"

urlpatterns = [
    path("buka/", views.buka_toko, name="buka_toko"),
    path("saya/", views.toko_saya, name="toko_saya"),
    path("<str:username>/", views.detail, name="detail"),
]
