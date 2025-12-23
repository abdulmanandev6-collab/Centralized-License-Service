"""
Unit tests for license service models.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from licenses.models import Activation, Brand, License, LicenseKey, LicenseStatus, Product


@pytest.mark.django_db
class TestBrand:
    def test_create_brand(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-api-key-123")
        assert brand.name == "Test Brand"
        assert brand.api_key == "test-api-key-123"
        assert brand.is_active is True
        assert brand.id is not None

    def test_brand_str(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        assert str(brand) == "Test Brand"

    def test_brand_is_authenticated(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        assert brand.is_authenticated is True


@pytest.mark.django_db
class TestProduct:
    def test_create_product(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        product = Product.objects.create(brand=brand, name="Test Product", slug="test-product")
        assert product.brand == brand
        assert product.name == "Test Product"
        assert product.slug == "test-product"
        assert product.is_active is True

    def test_product_str(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        product = Product.objects.create(brand=brand, name="Test Product", slug="test-product")
        assert str(product) == "Test Brand - Test Product"

    def test_product_unique_per_brand(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        Product.objects.create(brand=brand, name="Product", slug="test")

        brand2 = Brand.objects.create(name="Brand 2", api_key="key2")
        Product.objects.create(brand=brand2, name="Product", slug="test")

        with pytest.raises(Exception):
            Product.objects.create(brand=brand, name="Product 2", slug="test")


@pytest.mark.django_db
class TestLicenseKey:
    def test_create_license_key(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        license_key = LicenseKey.objects.create(
            key="TEST-1234-5678", brand=brand, customer_email="test@example.com"
        )
        assert license_key.key == "TEST-1234-5678"
        assert license_key.brand == brand
        assert license_key.customer_email == "test@example.com"

    def test_license_key_str(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )
        assert "TEST-1234" in str(license_key)
        assert "Test Brand" in str(license_key)


@pytest.mark.django_db
class TestLicense:
    def test_create_license(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        product = Product.objects.create(brand=brand, name="Product", slug="product")
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )

        license = License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.VALID, max_seats=5
        )

        assert license.license_key == license_key
        assert license.product == product
        assert license.status == LicenseStatus.VALID
        assert license.max_seats == 5

    def test_license_is_valid(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        product = Product.objects.create(brand=brand, name="Product", slug="product")
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )

        license = License.objects.create(
            license_key=license_key,
            product=product,
            status=LicenseStatus.VALID,
            expiration_date=timezone.now() + timedelta(days=30),
        )
        assert license.is_valid is True

        expired_license = License.objects.create(
            license_key=license_key,
            product=product,
            status=LicenseStatus.VALID,
            expiration_date=timezone.now() - timedelta(days=1),
        )
        assert expired_license.is_valid is False

        suspended = License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.SUSPENDED
        )
        assert suspended.is_valid is False

        cancelled = License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.CANCELLED
        )
        assert cancelled.is_valid is False


@pytest.mark.django_db
class TestActivation:
    def test_create_activation(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        product = Product.objects.create(brand=brand, name="Product", slug="product")
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )
        license = License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.VALID
        )

        activation = Activation.objects.create(
            license=license, instance_id="https://example.com", is_active=True
        )

        assert activation.license == license
        assert activation.instance_id == "https://example.com"
        assert activation.is_active is True
        assert activation.activated_at is not None

    def test_activation_str(self):
        brand = Brand.objects.create(name="Test Brand", api_key="test-key")
        product = Product.objects.create(brand=brand, name="Product", slug="product")
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )
        license = License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.VALID
        )
        activation = Activation.objects.create(license=license, instance_id="https://example.com")
        assert "Product" in str(activation)
        assert "example.com" in str(activation)
