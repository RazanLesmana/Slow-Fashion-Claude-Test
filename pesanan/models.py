import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from listing.models import Product
from .constants import (
    PAYMENT_CHOICES, STATUS_CHOICES, STATUS_DIBATALKAN, STATUS_DIKIRIM, STATUS_DIPROSES, STATUS_SELESAI,
)

phone_validator = RegexValidator(
    regex=r"^(08|628)\d{7,11}$",
    message="No. HP harus diawali 08 atau 62 dan berisi 10–14 digit angka.",
)
postal_code_validator = RegexValidator(
    regex=r"^\d{5}$",
    message="Kode pos harus 5 digit angka.",
)


def store_name_for(user):
    """Nama toko seller (app profil_toko), fallback ke username."""
    store = getattr(user, "store", None)  # RelatedObjectDoesNotExist turunan AttributeError
    return store.name if store else user.username


class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_cart_item"),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.product.name}"


class Order(models.Model):
    code = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    checkout_ref = models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="incoming_orders",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DIPROSES)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="transfer")

    # Snapshot alamat pengiriman saat checkout
    recipient_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    address = models.TextField(max_length=300)
    city = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=5, validators=[postal_code_validator])

    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.code or f"Order #{self.pk}"

    def save(self, *args, **kwargs):
        self.total = (self.subtotal or 0) + (self.shipping_fee or 0)
        super().save(*args, **kwargs)
        # Kode dibuat dari pk supaya pasti unik dan aman dipanggil berulang.
        if not self.code:
            self.code = f"LPK-{self.pk:04d}"
            Order.objects.filter(pk=self.pk).update(code=self.code)

    # ----- Helper hak akses & transisi status -----

    def is_participant(self, user):
        return user.is_authenticated and user.pk in (self.buyer_id, self.seller_id)

    def can_ship(self, user):
        return user.is_authenticated and user.pk == self.seller_id and self.status == STATUS_DIPROSES

    def can_complete(self, user):
        return user.is_authenticated and user.pk == self.buyer_id and self.status == STATUS_DIKIRIM

    def can_cancel(self, user):
        return self.is_participant(user) and self.status == STATUS_DIPROSES

    def mark_shipped(self):
        self.status = STATUS_DIKIRIM
        self.shipped_at = timezone.now()
        self.save(update_fields=["status", "shipped_at"])

    def mark_completed(self):
        self.status = STATUS_SELESAI
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

    def cancel(self, user):
        """Batalkan pesanan; produk yang masih ada kembali dijual (status active)."""
        self.status = STATUS_DIBATALKAN
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.save(update_fields=["status", "cancelled_at", "cancelled_by"])
        product_ids = self.items.exclude(product=None).values_list("product_id", flat=True)
        Product.objects.filter(pk__in=list(product_ids), status="sold").update(status="active")

    @property
    def store_name(self):
        return store_name_for(self.seller)

    @property
    def step_index(self):
        """Posisi di stepper Diproses → Dikirim → Selesai (0-2)."""
        return {STATUS_DIPROSES: 0, STATUS_DIKIRIM: 1, STATUS_SELESAI: 2}.get(self.status, -1)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # SET_NULL supaya riwayat pesanan tetap ada walau listing dihapus seller.
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=30)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.product_name} ({self.order})"
