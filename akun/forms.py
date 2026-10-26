from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile

class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "password1", "password2"]

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["bio"]
        widgets = {
            "bio": forms.Textarea(attrs={
                "rows": 4,
                "maxlength": 200,
                "placeholder": "Ceritakan sedikit tentang dirimu atau gaya berpakaianmu.",
            }),
        }
        labels = {"bio": "Bio"}
