from django import forms

from .models import SizeChart, Store, normalize_whatsapp


class StoreForm(forms.ModelForm):
    # Didefinisikan ulang supaya input dengan spasi/strip (lebih dari 15 karakter)
    # tidak ditolak sebelum dinormalisasi di clean_whatsapp_number.
    whatsapp_number = forms.CharField(
        label="No. WhatsApp",
        max_length=20,
        help_text="Hanya terlihat oleh pengguna yang sudah masuk.",
        widget=forms.TextInput(attrs={"placeholder": "0812 3456 7890", "inputmode": "tel"}),
    )

    class Meta:
        model = Store
        fields = ["name", "city", "description", "whatsapp_number"]
        labels = {
            "name": "Nama toko",
            "city": "Kota",
            "description": "Deskripsi",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Contoh: Rara Preloved"}),
            "city": forms.TextInput(attrs={"placeholder": "Contoh: Jakarta Selatan"}),
            "description": forms.Textarea(attrs={
                "rows": 3,
                "maxlength": 300,
                "placeholder": "Barang apa yang biasanya kamu jual?",
            }),
        }

    def clean_whatsapp_number(self):
        # Validator format (08/62) dijalankan model setelah nomor dinormalisasi.
        return normalize_whatsapp(self.cleaned_data["whatsapp_number"])

    def clean_name(self):
        return self.cleaned_data["name"].strip()


class SizeChartForm(forms.ModelForm):

    class Meta:
        model = SizeChart
        fields = ["brand", "size", "chest_cm", "length_cm"]
        labels = {
            "brand": "Brand",
            "size": "Size",
            "chest_cm": "Lingkar dada (cm)",
            "length_cm": "Panjang (cm)",
        }
        widgets = {
            "brand": forms.TextInput(attrs={"placeholder": "Contoh: Uniqlo"}),
            "size": forms.TextInput(attrs={"placeholder": "Contoh: M"}),
        }

    def clean_brand(self):
        return self.cleaned_data["brand"].strip()

    def clean_size(self):
        return self.cleaned_data["size"].strip().upper()
