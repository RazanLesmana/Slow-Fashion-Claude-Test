from django import forms

from .models import RATING_CHOICES, Review


class ReviewForm(forms.ModelForm):
    """
    Form ulasan. `author` dan target (`product` atau `seller`) diberikan view,
    supaya validasi "tidak boleh mengulas milik sendiri" dan "sekali saja"
    bisa dicek di sini sebelum menyimpan.
    """

    rating = forms.TypedChoiceField(
        label="Rating",
        choices=RATING_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={"required": "Pilih rating 1–5 bintang."},
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        labels = {"comment": "Komentar"}
        widgets = {
            "comment": forms.Textarea(attrs={
                "rows": 3,
                "maxlength": 1000,
                "placeholder": "Bagaimana kondisi barang dan pelayanan seller?",
            }),
        }

    def __init__(self, *args, author=None, product=None, seller=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.author = author
        if self.instance.pk:
            product, seller = self.instance.product, self.instance.seller
        else:
            self.instance.author = author
            self.instance.product = product
            self.instance.seller = seller
        self.product = product
        self.seller = seller

    def clean_comment(self):
        comment = self.cleaned_data["comment"].strip()
        if not comment:
            raise forms.ValidationError("Komentar tidak boleh kosong.")
        return comment

    def clean(self):
        cleaned = super().clean()
        if self.author is None or self.instance.pk:
            return cleaned

        if self.product is not None:
            if self.product.seller_id == self.author.pk:
                raise forms.ValidationError("Kamu tidak bisa mengulas produkmu sendiri.")
            if Review.objects.filter(author=self.author, product=self.product).exists():
                raise forms.ValidationError("Kamu sudah mengulas produk ini.")
        elif self.seller is not None:
            if self.seller.pk == self.author.pk:
                raise forms.ValidationError("Kamu tidak bisa mengulas tokomu sendiri.")
            if Review.objects.filter(author=self.author, seller=self.seller).exists():
                raise forms.ValidationError("Kamu sudah mengulas toko ini.")
        return cleaned
