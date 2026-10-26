from django import forms

from .models import Order

ADDRESS_FIELDS = ["recipient_name", "phone", "address", "city", "postal_code"]


class CheckoutForm(forms.ModelForm):

    class Meta:
        model = Order
        fields = ADDRESS_FIELDS + ["payment_method"]
        labels = {
            "recipient_name": "Nama penerima",
            "phone": "No. HP",
            "address": "Alamat",
            "city": "Kota",
            "postal_code": "Kode pos",
            "payment_method": "Metode pembayaran",
        }
        widgets = {
            "recipient_name": forms.TextInput(attrs={"placeholder": "Nama lengkap", "autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"placeholder": "0812 3456 7890", "inputmode": "tel", "autocomplete": "tel"}),
            "address": forms.Textarea(attrs={
                "rows": 3, "maxlength": 300,
                "placeholder": "Nama jalan, nomor rumah, RT/RW, kelurahan, kecamatan",
                "autocomplete": "street-address",
            }),
            "city": forms.TextInput(attrs={"placeholder": "Contoh: Depok", "autocomplete": "address-level2"}),
            "postal_code": forms.TextInput(attrs={
                "placeholder": "16424", "inputmode": "numeric", "maxlength": 5, "autocomplete": "postal-code",
            }),
            "payment_method": forms.RadioSelect,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Prefill alamat dari pesanan terakhir supaya tidak perlu ketik ulang.
        if user is not None and not self.is_bound:
            last = Order.objects.filter(buyer=user).order_by("-created_at", "-pk").first()
            if last:
                for field in ADDRESS_FIELDS:
                    self.initial.setdefault(field, getattr(last, field))
            self.initial.setdefault("payment_method", "transfer")

    def clean_phone(self):
        # "+62 812-3456-7890" -> "6281234567890"; format dicek validator model.
        return "".join(ch for ch in self.cleaned_data["phone"] if ch.isdigit())

    def clean_postal_code(self):
        return self.cleaned_data["postal_code"].strip()

    def address_data(self):
        return {field: self.cleaned_data[field] for field in ADDRESS_FIELDS}
