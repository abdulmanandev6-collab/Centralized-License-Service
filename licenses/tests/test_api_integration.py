"""
Integration tests for API endpoints.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from licenses.models import Activation, Brand, License, LicenseKey, LicenseStatus, Product


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def brand():
    return Brand.objects.create(name="Test Brand", api_key="test-api-key-123", is_active=True)


@pytest.fixture
def product(brand):
    return Product.objects.create(
        brand=brand, name="Test Product", slug="test-product", is_active=True
    )


@pytest.mark.django_db
class TestBrandAPI:
    def test_provision_license(self, api_client, brand, product):
        url = "/api/brand/licenses/"
        api_client.credentials(HTTP_X_API_KEY=brand.api_key)

        data = {
            "customer_email": "test@example.com",
            "products": [
                {"slug": "test-product", "expiration_date": "2025-12-31T23:59:59", "max_seats": 5}
            ],
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == 201
        assert "license_key" in response.data
        assert response.data["status"] == "success"
        assert len(response.data["licenses"]) == 1

    def test_provision_license_requires_auth(self, api_client):
        url = "/api/brand/licenses/"
        data = {"customer_email": "test@example.com", "products": []}
        response = api_client.post(url, data, format="json")
        assert response.status_code == 403

    def test_add_product_to_license_key(self, api_client, brand, product):
        license_key = LicenseKey.objects.create(
            key="TEST-1234-5678", brand=brand, customer_email="test@example.com"
        )
        License.objects.create(license_key=license_key, product=product, status=LicenseStatus.VALID)

        Product.objects.create(brand=brand, name="Product 2", slug="product-2")

        url = f"/api/brand/licenses/{license_key.key}/add-product/"
        api_client.credentials(HTTP_X_API_KEY=brand.api_key)

        data = {"product_slug": "product-2", "expiration_date": "2025-12-31T23:59:59"}

        response = api_client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["status"] == "success"

    def test_list_licenses_by_email(self, api_client, brand, product):
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )
        License.objects.create(license_key=license_key, product=product, status=LicenseStatus.VALID)

        url = "/api/brand/licenses/by-email/"
        api_client.credentials(HTTP_X_API_KEY=brand.api_key)

        response = api_client.get(url, {"email": "test@example.com"})
        assert response.status_code == 200
        assert len(response.data) > 0

    def test_update_license_lifecycle(self, api_client, brand, product):
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )
        license_obj = License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.VALID
        )

        url = f"/api/brand/licenses/{license_obj.id}/lifecycle/"
        api_client.credentials(HTTP_X_API_KEY=brand.api_key)

        data = {"action": "suspend"}
        response = api_client.patch(url, data, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "success"

        license_obj.refresh_from_db()
        assert license_obj.status == LicenseStatus.SUSPENDED


@pytest.mark.django_db
class TestProductAPI:
    def test_activate_license(self, api_client, brand, product):
        license_key = LicenseKey.objects.create(
            key="TEST-1234-5678", brand=brand, customer_email="test@example.com"
        )
        License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.VALID, max_seats=5
        )

        url = reverse("activate-license")
        api_client.credentials(HTTP_X_LICENSE_KEY=license_key.key)

        data = {"instance_id": "https://example.com", "product_slug": "test-product"}

        response = api_client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["status"] == "success"
        assert "activation_id" in response.data

    def test_activate_license_requires_auth(self, api_client):
        url = "/api/product/activate/"
        data = {"instance_id": "https://example.com", "product_slug": "test"}
        response = api_client.post(url, data, format="json")
        assert response.status_code == 403

    def test_check_license_status(self, api_client, brand, product):
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )
        License.objects.create(license_key=license_key, product=product, status=LicenseStatus.VALID)

        url = "/api/product/check/"
        api_client.credentials(HTTP_X_LICENSE_KEY=license_key.key)

        response = api_client.get(url)
        assert response.status_code == 200
        assert "license_key" in response.data
        assert response.data["license_key"] == license_key.key
        assert "licenses" in response.data

    def test_deactivate_seat(self, api_client, brand, product):
        license_key = LicenseKey.objects.create(
            key="TEST-1234", brand=brand, customer_email="test@example.com"
        )
        license_obj = License.objects.create(
            license_key=license_key, product=product, status=LicenseStatus.VALID, max_seats=5
        )
        activation = Activation.objects.create(
            license=license_obj, instance_id="https://example.com", is_active=True
        )

        url = "/api/product/deactivate/"
        api_client.credentials(HTTP_X_LICENSE_KEY=license_key.key)

        data = {"instance_id": "https://example.com", "product_slug": "test-product"}

        response = api_client.post(url, data, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "success"

        activation.refresh_from_db()
        assert activation.is_active is False


@pytest.mark.django_db
class TestHealthCheck:
    def test_health_check(self, api_client):
        url = "/api/health/"
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["status"] == "healthy"
