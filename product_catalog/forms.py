from django import forms

from .models import WishlistItem


class WishlistNoteForm(forms.ModelForm):

    class Meta:
        model = WishlistItem
        fields = ["note"]
        labels = {"note": "Catatan"}
        widgets = {
            "note": forms.TextInput(attrs={
                "maxlength": 200,
                "placeholder": "Mis. cocok buat kondangan, tunggu gajian",
            }),
        }
