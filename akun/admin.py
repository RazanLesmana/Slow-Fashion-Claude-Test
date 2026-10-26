from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_seller", "created_at")
    list_filter = ("is_seller",)
    search_fields = ("user__username",)
