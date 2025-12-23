from django.contrib import admin

from .models import Activation, Brand, License, LicenseKey, Product


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "api_key", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "slug", "is_active", "created_at"]
    list_filter = ["brand", "is_active", "created_at"]
    search_fields = ["name", "slug"]


@admin.register(LicenseKey)
class LicenseKeyAdmin(admin.ModelAdmin):
    list_display = ["key", "brand", "customer_email", "created_at"]
    list_filter = ["brand", "created_at"]
    search_fields = ["key", "customer_email"]


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "license_key",
        "status",
        "expiration_date",
        "max_seats",
        "created_at",
    ]
    list_filter = ["status", "product__brand", "created_at"]
    search_fields = ["license_key__key", "product__name"]


@admin.register(Activation)
class ActivationAdmin(admin.ModelAdmin):
    list_display = ["license", "instance_id", "is_active", "activated_at", "deactivated_at"]
    list_filter = ["is_active", "activated_at", "license__product__brand"]
    search_fields = ["instance_id", "license__license_key__key"]
