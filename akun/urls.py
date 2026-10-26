from django.urls import path
from . import views

app_name = "akun"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profil/", views.profil, name="profil"),
    path("profil/edit/", views.edit_profil, name="edit_profil"),
    path("hapus/", views.hapus_akun, name="hapus_akun"),
    path("toggle-seller/", views.toggle_seller, name="toggle_seller"),
    path("json/", views.profil_json, name="profil_json"),
]
