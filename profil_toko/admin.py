from django.contrib import admin

from .models import SizeChart, Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "city", "created_at")
    search_fields = ("name", "owner__username", "city")


@admin.register(SizeChart)
class SizeChartAdmin(admin.ModelAdmin):
    list_display = ("brand", "size", "chest_cm", "length_cm", "created_by")
    list_filter = ("brand",)
    search_fields = ("brand",)
