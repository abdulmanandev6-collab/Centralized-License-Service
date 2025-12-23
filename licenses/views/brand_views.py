"""
Views for Brand API endpoints.
"""

import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from licenses.models import Activation, License, LicenseKey, LicenseStatus, Product
from licenses.serializers import (
    AddProductToLicenseRequestSerializer,
    LicenseSerializer,
    ProvisionLicenseRequestSerializer,
    UpdateLicenseLifecycleSerializer,
)
from licenses.utils import generate_license_key

logger = logging.getLogger(__name__)


class ProvisionLicenseView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="US 1: Provision License",
        operation_description="Creates a new license key and licenses for a customer. You can add multiple products at once.",
        tags=["US 1: Brand Provision License"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["customer_email", "products"],
            properties={
                "customer_email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description="Customer email",
                    example="john@example.com",
                ),
                "products": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="Products to create licenses for",
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        required=["slug"],
                        properties={
                            "slug": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Product slug (e.g., rankmath)",
                                example="rankmath",
                            ),
                            "expiration_date": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                format=openapi.FORMAT_DATETIME,
                                description="When license expires (optional)",
                                example="2025-12-31T23:59:59Z",
                            ),
                            "max_seats": openapi.Schema(
                                type=openapi.TYPE_INTEGER,
                                description="Max activations (optional)",
                                example=5,
                            ),
                        },
                    ),
                ),
            },
            example={
                "customer_email": "john@example.com",
                "products": [
                    {"slug": "rankmath", "expiration_date": "2025-12-31T23:59:59Z", "max_seats": 3}
                ],
            },
        ),
        responses={
            201: "Success",
            400: "Bad request",
            404: "Not found",
        },
        security=[{"X-API-Key": []}],
    )
    def post(self, request):
        brand = request.user

        serializer = ProvisionLicenseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        customer_email = serializer.validated_data["customer_email"]
        products_data = serializer.validated_data["products"]

        try:
            with transaction.atomic():
                license_key_obj, created = LicenseKey.objects.get_or_create(
                    brand=brand,
                    customer_email=customer_email,
                    defaults={"key": self._generate_unique_key()},
                )

                created_licenses = []
                for product_data in products_data:
                    product_slug = product_data.get("slug")
                    if not product_slug:
                        return Response(
                            {"error": "Product slug is required"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    try:
                        product = Product.objects.get(
                            brand=brand, slug=product_slug, is_active=True
                        )
                    except Product.DoesNotExist:
                        return Response(
                            {"error": f'Product "{product_slug}" not found for brand {brand.name}'},
                            status=status.HTTP_404_NOT_FOUND,
                        )

                    # Skip if license already exists for this product
                    existing = License.objects.filter(
                        license_key=license_key_obj, product=product
                    ).first()

                    if existing:
                        logger.warning(
                            f"License for {product_slug} already exists on key {license_key_obj.key}"
                        )
                        created_licenses.append(LicenseSerializer(existing).data)
                        continue

                    # Handle expiration date parsing
                    exp_date = product_data.get("expiration_date")
                    if exp_date:
                        if isinstance(exp_date, str):
                            try:
                                if exp_date.endswith("Z"):
                                    exp_date = exp_date[:-1] + "+00:00"
                                elif "+" not in exp_date and "T" in exp_date:
                                    exp_date = exp_date + "+00:00"
                                exp_date = datetime.fromisoformat(exp_date)
                                if not timezone.is_aware(exp_date):
                                    exp_date = timezone.make_aware(exp_date)
                            except (ValueError, AttributeError) as e:
                                logger.error(f"Date parsing error: {e}, input: {exp_date}")
                                return Response(
                                    {
                                        "error": f"Invalid expiration_date format for {product_slug}. Use ISO 8601 format (e.g., 2025-12-31T23:59:59Z)"
                                    },
                                    status=status.HTTP_400_BAD_REQUEST,
                                )
                        elif not timezone.is_aware(exp_date):
                            exp_date = timezone.make_aware(exp_date)

                    new_license = License.objects.create(
                        license_key=license_key_obj,
                        product=product,
                        status=LicenseStatus.VALID,
                        expiration_date=exp_date,
                        max_seats=product_data.get("max_seats"),
                    )
                    created_licenses.append(LicenseSerializer(new_license).data)

                result = {
                    "status": "success",
                    "message": "License provisioned successfully",
                    "license_key": license_key_obj.key,
                    "customer_email": license_key_obj.customer_email,
                    "brand": brand.name,
                    "licenses": created_licenses,
                    "created": created,
                }

                logger.info(
                    f"Provisioned {license_key_obj.key} for {customer_email} - {len(created_licenses)} license(s)"
                )
                return Response(result, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error provisioning license: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to provision license. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _generate_unique_key(self):
        """Generate a unique license key, retry if collision occurs."""
        for attempt in range(10):
            key = generate_license_key()
            if not LicenseKey.objects.filter(key=key).exists():
                return key
        raise Exception("Unable to generate unique license key after multiple attempts")


class AddProductToLicenseKeyView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="US 1: Add Product to License Key",
        operation_description="Adds another product license to an existing license key. Useful when customer buys an addon.",
        tags=["US 1: Brand Provision License"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["product_slug"],
            properties={
                "product_slug": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Product to add", example="content-ai"
                ),
                "expiration_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATETIME,
                    description="Optional expiration",
                    example="2025-12-31T23:59:59Z",
                ),
                "max_seats": openapi.Schema(
                    type=openapi.TYPE_INTEGER, description="Optional seat limit", example=5
                ),
            },
            example={
                "product_slug": "content-ai",
                "expiration_date": "2025-12-31T23:59:59Z",
                "max_seats": 5,
            },
        ),
        manual_parameters=[
            openapi.Parameter(
                "license_key",
                openapi.IN_PATH,
                type=openapi.TYPE_STRING,
                description="Existing license key",
                required=True,
                example="ABCD-1234-EFGH-5678",
            ),
        ],
        responses={201: "Success", 400: "Bad request", 404: "Not found"},
        security=[{"X-API-Key": []}],
    )
    def post(self, request, license_key):
        brand = request.user

        # Verify license key belongs to this brand
        try:
            lk = LicenseKey.objects.get(key=license_key, brand=brand)
        except LicenseKey.DoesNotExist:
            return Response(
                {"error": "License key not found or does not belong to your brand"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AddProductToLicenseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        product_slug = serializer.validated_data["product_slug"]

        try:
            product = Product.objects.get(brand=brand, slug=product_slug, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {"error": f'Product "{product_slug}" not found'}, status=status.HTTP_404_NOT_FOUND
            )

        # Prevent duplicate licenses
        if License.objects.filter(license_key=lk, product=product).exists():
            return Response(
                {"error": f"License for {product_slug} already exists for this key"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            exp_date = serializer.validated_data.get("expiration_date")
            if exp_date:
                if isinstance(exp_date, str):
                    try:
                        exp_date = exp_date.replace("Z", "+00:00")
                        exp_date = timezone.make_aware(datetime.fromisoformat(exp_date))
                    except (ValueError, AttributeError):
                        return Response(
                            {"error": "Invalid expiration_date format"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                elif not timezone.is_aware(exp_date):
                    exp_date = timezone.make_aware(exp_date)

            new_license = License.objects.create(
                license_key=lk,
                product=product,
                status=LicenseStatus.VALID,
                expiration_date=exp_date,
                max_seats=serializer.validated_data.get("max_seats"),
            )

            return Response(
                {
                    "status": "success",
                    "message": "Product added successfully",
                    "license_key": lk.key,
                    "license": LicenseSerializer(new_license).data,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Error adding product: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to add product to license key"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListLicensesByEmailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="US 6: List Licenses by Email",
        operation_description="Get all licenses for a customer across all brands. Useful for customer support.",
        tags=["US 6: Cross-Brand License Query"],
        manual_parameters=[
            openapi.Parameter(
                "email",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description="Customer email",
                required=True,
                example="user@example.com",
            ),
        ],
        responses={200: "Success", 400: "Bad request"},
        security=[{"X-API-Key": []}],
    )
    def get(self, request):
        email = request.query_params.get("email")

        if not email:
            return Response(
                {"error": "Email parameter is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            keys = (
                LicenseKey.objects.filter(customer_email=email)
                .select_related("brand")
                .prefetch_related("licenses__product")
            )

            if not keys.exists():
                return Response({"email": email, "licenses": []}, status=status.HTTP_200_OK)

            result = []
            for key in keys:
                for lic in key.licenses.all():
                    active = Activation.objects.filter(license=lic, is_active=True).count()

                    remaining = None
                    if lic.max_seats:
                        remaining = max(0, lic.max_seats - active)

                    result.append(
                        {
                            "license_key": key.key,
                            "brand": key.brand.name,
                            "product": lic.product.name,
                            "product_slug": lic.product.slug,
                            "status": lic.status,
                            "is_valid": lic.is_valid,
                            "expiration_date": lic.expiration_date,
                            "max_seats": lic.max_seats,
                            "active_seats": active,
                            "remaining_seats": remaining,
                            "created_at": lic.created_at,
                        }
                    )

            return Response(
                {"email": email, "total_licenses": len(result), "licenses": result},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error listing licenses by email: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve licenses"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UpdateLicenseLifecycleView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="US 2: Update License Lifecycle",
        operation_description="Change license status - suspend, resume, cancel, or extend expiration",
        tags=["US 2: License Lifecycle Management"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["action"],
            properties={
                "action": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["renew", "suspend", "resume", "cancel"],
                    description="What to do with the license",
                    example="suspend",
                ),
                "expiration_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATETIME,
                    description="New expiration date (needed for renew)",
                    example="2026-12-31T23:59:59Z",
                ),
            },
            example={"action": "suspend"},
        ),
        manual_parameters=[
            openapi.Parameter(
                "license_id",
                openapi.IN_PATH,
                description="License ID",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            ),
        ],
        responses={
            200: "Success",
            400: "Bad request",
            403: "Forbidden",
            404: "Not found",
        },
        security=[{"X-API-Key": []}],
    )
    def patch(self, request, license_id):
        brand = request.user

        try:
            lic = License.objects.select_related("license_key__brand", "product").get(id=license_id)
        except License.DoesNotExist:
            return Response({"error": "License not found"}, status=status.HTTP_404_NOT_FOUND)

        if lic.license_key.brand != brand:
            return Response(
                {"error": "License does not belong to your brand"}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = UpdateLicenseLifecycleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data["action"]

        try:
            with transaction.atomic():
                if action == "renew":
                    exp_date = serializer.validated_data.get("expiration_date")
                    if isinstance(exp_date, str):
                        exp_date = exp_date.replace("Z", "+00:00")
                        exp_date = timezone.make_aware(datetime.fromisoformat(exp_date))
                    elif exp_date and not timezone.is_aware(exp_date):
                        exp_date = timezone.make_aware(exp_date)

                    lic.expiration_date = exp_date
                    if lic.status == LicenseStatus.SUSPENDED:
                        lic.status = LicenseStatus.VALID
                    lic.save()
                    logger.info(f"Renewed {license_id} until {exp_date}")

                elif action == "suspend":
                    if lic.status == LicenseStatus.CANCELLED:
                        return Response(
                            {"error": "Cannot suspend cancelled license"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    lic.status = LicenseStatus.SUSPENDED
                    lic.save()
                    logger.info(f"Suspended {license_id}")

                elif action == "resume":
                    if lic.status != LicenseStatus.SUSPENDED:
                        return Response(
                            {"error": "License is not suspended"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    lic.status = LicenseStatus.VALID
                    lic.save()
                    logger.info(f"Resumed {license_id}")

                elif action == "cancel":
                    lic.status = LicenseStatus.CANCELLED
                    lic.save()
                    logger.info(f"Cancelled {license_id}")

                return Response(
                    {
                        "status": "success",
                        "message": f"License {action}ed successfully",
                        "license": LicenseSerializer(lic).data,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            logger.error(f"Error updating license: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update license"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
