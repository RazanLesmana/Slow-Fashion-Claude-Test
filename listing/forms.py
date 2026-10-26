
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
                "placeholder": "Contoh: Linen blazer krem",
            }),
            "brand": forms.TextInput(attrs={
                "placeholder": "Contoh: Uniqlo",
            }),
            "description": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Ceritakan kondisi, bahan, dan ukuran asli produk.",
            }),
            "category": forms.Select(),
            "size": forms.TextInput(attrs={
                "placeholder": "Contoh: M, L, atau All Size",
            }),
            "condition": forms.Select(),
            "price": forms.NumberInput(attrs={
                "min": "1",
                "step": "1",
                "placeholder": "Contoh: 85000",
            }),
        }

        labels = {
            "name": "Nama produk",
            "brand": "Brand",
            "description": "Deskripsi",
            "category": "Kategori",
            "size": "Size",
            "condition": "Kondisi",
            "price": "Harga",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = [("", "Pilih kategori")] + Product.CATEGORY_CHOICES
        self.fields["condition"].choices = [("", "Pilih kondisi")] + Product.CONDITION_CHOICES
        # Harga rupiah ditampilkan tanpa desimal (85000, bukan 85000.00).
        if self.instance.pk and not self.is_bound:
            self.initial["price"] = int(self.instance.price)

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
        widgets = {
            "image": forms.ClearableFileInput(attrs={
                "accept": "image/jpeg,image/png,image/webp",
            }),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and getattr(image, "size", 0) > 5 * 1024 * 1024:
            raise forms.ValidationError("Ukuran foto maksimal 5 MB.")
        return image


ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    extra=5,
    can_delete=True,
    max_num=5,
    validate_max=True,
)
