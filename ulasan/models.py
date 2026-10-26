from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from listing.models import Product

RATING_CHOICES = [(i, f"{i} bintang") for i in range(1, 6)]


class Review(models.Model):
    """
    Ulasan untuk satu produk ATAU satu toko. Toko diwakili oleh User pemiliknya
    (field `seller`), jadi app ini tidak bergantung pada model Store.
    """
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reviews",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="store_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=False, seller__isnull=True)
                    | Q(product__isnull=True, seller__isnull=False)
                ),
                name="review_exactly_one_target",
                violation_error_message="Ulasan harus untuk tepat satu produk atau satu toko.",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="review_rating_1_to_5",
            ),
            models.UniqueConstraint(
                fields=["author", "product"],
                condition=Q(product__isnull=False),
                name="unique_product_review_per_author",
                violation_error_message="Kamu sudah mengulas produk ini.",
            ),
            models.UniqueConstraint(
                fields=["author", "seller"],
                condition=Q(seller__isnull=False),
                name="unique_store_review_per_author",
                violation_error_message="Kamu sudah mengulas toko ini.",
            ),
        ]

    def __str__(self):
        target = self.product.name if self.product_id else f"toko {self.seller.username}"
        return f"{self.author.username} → {target} ({self.rating}★)"

    @property
    def target_owner_id(self):
        return self.product.seller_id if self.product_id else self.seller_id
