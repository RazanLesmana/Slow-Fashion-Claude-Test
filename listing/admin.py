from django.contrib import admin

from .models import Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "seller", "brand", "category", "price", "status", "created_at")
    list_filter = ("status", "category", "condition")
    search_fields = ("name", "brand", "seller__username")
    inlines = [ProductImageInline]
