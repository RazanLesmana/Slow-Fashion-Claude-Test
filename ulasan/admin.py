from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("author", "product", "seller", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("author__username", "product__name", "seller__username", "comment")
