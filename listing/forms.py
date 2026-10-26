
from django import forms
from django.forms import inlineformset_factory

from .models import Product, ProductImage


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product

        # Fields the seller is allowed to enter or edit.
        # seller, status, and timestamps are handled separately.
        fields = [
            "name",
            "brand",
            "description",
            "category",
            "size",
            "condition",
            "price",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Contoh: Pink Cardigan",
            }),
            "brand": forms.TextInput(attrs={
                "placeholder": "Contoh: Uniqlo",
            }),
            "description": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Describe your product...",
            }),
            "category": forms.Select(),
            "size": forms.TextInput(attrs={
                "placeholder": "Contoh: M, L, atau All Size",
            }),
            "condition": forms.Select(),
            "price": forms.NumberInput(attrs={
                "min": "0.01",
                "step": "0.01",
                "placeholder": "Contoh: 150000",
            }),
        }

    def clean_price(self):
        price = self.cleaned_data["price"]

        if price <= 0:
            raise forms.ValidationError(
                "Harga produk harus lebih besar dari 0."
            )

        return price


class ProductImageForm(forms.ModelForm):

    class Meta:
        model = ProductImage
        fields = ["image", "alt_text"]


ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    extra=3,
    can_delete=True,
    max_num=5,
    validate_max=True,
)
