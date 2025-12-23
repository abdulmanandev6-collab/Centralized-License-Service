"""
Core models for the License Service.
"""

import uuid

from django.db import models
from django.utils import timezone


class Brand(models.Model):
    """
    Represents a brand/tenant in the multi-tenant system.
    Each brand is isolated but can query across brands when needed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    api_key = models.CharField(
        max_length=255, unique=True, help_text="API key for brand authentication"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "brands"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_authenticated(self):
        """Required by DRF's IsAuthenticated permission."""
        return True


class Product(models.Model):
    """
    Represents a product that can be licensed.
    Products belong to a specific brand.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "products"
        unique_together = ["brand", "slug"]
        ordering = ["brand", "name"]

    def __str__(self):
        return f"{self.brand.name} - {self.name}"


class LicenseKey(models.Model):
    """
    Represents a license key that can unlock one or more licenses.
    License keys are brand-specific and associated with a customer email.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255, unique=True, db_index=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="license_keys")
    customer_email = models.EmailField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "license_keys"
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["customer_email"]),
            models.Index(fields=["brand", "customer_email"]),
        ]

    def __str__(self):
        return f"{self.key} ({self.brand.name})"

    @property
    def is_authenticated(self):
        """Required by DRF's IsAuthenticated permission."""
        return True


class LicenseStatus(models.TextChoices):
    VALID = "valid", "Valid"
    SUSPENDED = "suspended", "Suspended"
    CANCELLED = "cancelled", "Cancelled"


class License(models.Model):
    """
    Represents a license for a specific product.
    Each license belongs to a license key and has a status and expiration date.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license_key = models.ForeignKey(LicenseKey, on_delete=models.CASCADE, related_name="licenses")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="licenses")
    status = models.CharField(
        max_length=20, choices=LicenseStatus.choices, default=LicenseStatus.VALID
    )
    expiration_date = models.DateTimeField(null=True, blank=True)
    max_seats = models.IntegerField(
        null=True, blank=True, help_text="Maximum number of activations allowed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "licenses"
        indexes = [
            models.Index(fields=["license_key", "status"]),
            models.Index(fields=["product", "status"]),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.status}"

    @property
    def is_valid(self):
        """Check if license is currently valid."""
        if self.status != LicenseStatus.VALID:
            return False
        if self.expiration_date and self.expiration_date < timezone.now():
            return False
        return True


class Activation(models.Model):
    """
    Represents an activation of a license for a specific instance.
    Each activation consumes a seat if seat management is enabled.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name="activations")
    instance_id = models.CharField(max_length=255, help_text="Site URL, host, machine ID, etc.")
    activated_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "activations"
        indexes = [
            models.Index(fields=["license", "is_active"]),
            models.Index(fields=["instance_id"]),
        ]
        unique_together = ["license", "instance_id", "is_active"]

    def __str__(self):
        return f"{self.license.product.name} - {self.instance_id}"
