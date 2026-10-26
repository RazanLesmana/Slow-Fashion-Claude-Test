from django.db import models

from django.conf import settings
from django.db import models


class Product(models.Model):

    CATEGORY_CHOICES = [
        ("atasan", "Atasan"),
        ("bawahan", "Bawahan"),
        ("outerwear", "Outerwear"),
        ("dress", "Dress"),
        ("sepatu", "Sepatu"),
        ("tas", "Tas"),
        ("aksesori", "Aksesori"),
        ("lainnya", "Lainnya"),
    ]

    CONDITION_CHOICES = [
        ("new", "Baru"),
        ("like_new", "Seperti Baru"),
        ("good", "Baik"),
        ("fair", "Cukup Baik"),
    ]

    STATUS_CHOICES = [
        ("active", "Aktif"),
        ("sold", "Terjual"),
    ]

    # The account that owns this listing
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_listings"
    )

    # Product information
    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField()

    # Category, size, and condition
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES
    )

    size = models.CharField(max_length=30)

    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES
    )

    # Price in Indonesian rupiah
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    # Every new listing starts as active
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProductImage(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(
        upload_to="product_images/"
    )

    alt_text = models.CharField(
        max_length=150,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name}"