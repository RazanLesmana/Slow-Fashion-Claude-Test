from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower

whatsapp_validator = RegexValidator(
    regex=r"^(08|628)\d{7,11}$",
    message="Nomor WhatsApp harus diawali 08 atau 62 dan berisi 10–14 digit angka.",
)


def normalize_whatsapp(value):
    """Buang spasi, strip, titik, dan tanda + (mis. '+62 812-3456' -> '628123456')."""
    return "".join(ch for ch in (value or "") if ch.isdigit())


class Store(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store",
    )
    name = models.CharField(max_length=80)
    city = models.CharField(max_length=80)
    description = models.TextField(max_length=300, blank=True)
    whatsapp_number = models.CharField(max_length=15, validators=[whatsapp_validator])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def initial(self):
        return (self.name[:1] or self.owner.username[:1]).upper()

    @property
    def whatsapp_international(self):
        """Format untuk wa.me: 0812... -> 62812..."""
        number = normalize_whatsapp(self.whatsapp_number)
        return "62" + number[1:] if number.startswith("0") else number

    @property
    def whatsapp_url(self):
        return f"https://wa.me/{self.whatsapp_international}"


SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"]


def size_sort_key(size):
    size = size.upper()
    if size in SIZE_ORDER:
        return (0, SIZE_ORDER.index(size), size)
    return (1, 0, size)


class SizeChart(models.Model):
    brand = models.CharField(max_length=60)
    size = models.CharField(max_length=10)
    chest_cm = models.PositiveSmallIntegerField(
        "lingkar dada (cm)",
        validators=[MinValueValidator(30), MaxValueValidator(250)],
    )
    length_cm = models.PositiveSmallIntegerField(
        "panjang (cm)",
        validators=[MinValueValidator(20), MaxValueValidator(200)],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="size_charts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["brand", "size"]
        constraints = [
            models.UniqueConstraint(
                Lower("brand"),
                Lower("size"),
                name="unique_size_chart_brand_size",
                violation_error_message="Size chart untuk brand dan size ini sudah ada.",
            ),
        ]

    def __str__(self):
        return f"{self.brand} {self.size}"

    def can_manage(self, user):
        return user.is_authenticated and (user.is_superuser or self.created_by_id == user.pk)

    def to_dict(self):
        return {
            "id": self.pk,
            "brand": self.brand,
            "size": self.size,
            "chest_cm": self.chest_cm,
            "length_cm": self.length_cm,
            "created_by": self.created_by.username if self.created_by else None,
        }
