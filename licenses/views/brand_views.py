"""
Views for Brand API endpoints.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from licenses.models import Brand, Product, LicenseKey, License, LicenseStatus
from licenses.serializers import (
    ProvisionLicenseRequestSerializer,
    AddProductToLicenseRequestSerializer,
    LicenseSerializer
)
from licenses.utils import generate_license_key
import logging

logger = logging.getLogger(__name__)


class ProvisionLicenseView(APIView):
    """
    US1: Brand can provision a license
    Creates a license key and license(s) for a customer email.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        brand = request.user
        
        serializer = ProvisionLicenseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        customer_email = serializer.validated_data['customer_email']
        products_data = serializer.validated_data['products']
        
        try:
            with transaction.atomic():
                # Reuse existing license key for same brand+email, or create new one
                license_key_obj, created = LicenseKey.objects.get_or_create(
                    brand=brand,
                    customer_email=customer_email,
                    defaults={'key': self._generate_unique_key()}
                )
                
                created_licenses = []
                for product_data in products_data:
                    product_slug = product_data.get('slug')
                    if not product_slug:
                        return Response(
                            {'error': 'Product slug is required'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    try:
                        product = Product.objects.get(brand=brand, slug=product_slug, is_active=True)
                    except Product.DoesNotExist:
                        return Response(
                            {'error': f'Product "{product_slug}" not found for brand {brand.name}'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    
                    # Skip if license already exists for this product
                    existing = License.objects.filter(
                        license_key=license_key_obj,
                        product=product
                    ).first()
                    
                    if existing:
                        logger.warning(f'License for {product_slug} already exists on key {license_key_obj.key}')
                        created_licenses.append(LicenseSerializer(existing).data)
                        continue
                    
                    # Handle expiration date parsing
                    exp_date = product_data.get('expiration_date')
                    if exp_date:
                        if isinstance(exp_date, str):
                            try:
                                exp_date = exp_date.replace('Z', '+00:00')
                                exp_date = timezone.make_aware(datetime.fromisoformat(exp_date))
                            except (ValueError, AttributeError):
                                return Response(
                                    {'error': f'Invalid expiration_date format for {product_slug}'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        elif not timezone.is_aware(exp_date):
                            exp_date = timezone.make_aware(exp_date)
                    
                    new_license = License.objects.create(
                        license_key=license_key_obj,
                        product=product,
                        status=LicenseStatus.VALID,
                        expiration_date=exp_date,
                        max_seats=product_data.get('max_seats')
                    )
                    created_licenses.append(LicenseSerializer(new_license).data)
                
                result = {
                    'license_key': license_key_obj.key,
                    'customer_email': license_key_obj.customer_email,
                    'brand': brand.name,
                    'licenses': created_licenses,
                    'created': created
                }
                
                logger.info(f'Provisioned {license_key_obj.key} for {customer_email} - {len(created_licenses)} license(s)')
                return Response(result, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f'Error provisioning license: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to provision license. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_unique_key(self):
        """Generate a unique license key, retry if collision occurs."""
        for attempt in range(10):
            key = generate_license_key()
            if not LicenseKey.objects.filter(key=key).exists():
                return key
        raise Exception('Unable to generate unique license key after multiple attempts')


class AddProductToLicenseKeyView(APIView):
    """
    US1: Add a product license to an existing license key
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, license_key):
        brand = request.user
        
        # Verify license key belongs to this brand
        try:
            lk = LicenseKey.objects.get(key=license_key, brand=brand)
        except LicenseKey.DoesNotExist:
            return Response(
                {'error': 'License key not found or does not belong to your brand'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AddProductToLicenseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        product_slug = serializer.validated_data['product_slug']
        
        try:
            product = Product.objects.get(brand=brand, slug=product_slug, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {'error': f'Product "{product_slug}" not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Prevent duplicate licenses
        if License.objects.filter(license_key=lk, product=product).exists():
            return Response(
                {'error': f'License for {product_slug} already exists for this key'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            exp_date = serializer.validated_data.get('expiration_date')
            if exp_date:
                if isinstance(exp_date, str):
                    try:
                        exp_date = exp_date.replace('Z', '+00:00')
                        exp_date = timezone.make_aware(datetime.fromisoformat(exp_date))
                    except (ValueError, AttributeError):
                        return Response(
                            {'error': 'Invalid expiration_date format'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                elif not timezone.is_aware(exp_date):
                    exp_date = timezone.make_aware(exp_date)
            
            new_license = License.objects.create(
                license_key=lk,
                product=product,
                status=LicenseStatus.VALID,
                expiration_date=exp_date,
                max_seats=serializer.validated_data.get('max_seats')
            )
            
            return Response({
                'license_key': lk.key,
                'license': LicenseSerializer(new_license).data,
                'message': 'Product added successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f'Error adding product: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to add product to license key'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ListLicensesByEmailView(APIView):
    """
    US6: Brands can list licenses by customer email across all brands
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Implementation will be added in US6
        return Response({'message': 'To be implemented'}, status=status.HTTP_501_NOT_IMPLEMENTED)

