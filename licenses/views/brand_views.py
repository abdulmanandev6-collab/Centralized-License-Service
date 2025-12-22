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
from licenses.models import Brand, Product, LicenseKey, License, LicenseStatus, Activation
from licenses.serializers import (
    ProvisionLicenseRequestSerializer,
    AddProductToLicenseRequestSerializer,
    LicenseSerializer,
    UpdateLicenseLifecycleSerializer
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
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        email = request.query_params.get('email')
        
        if not email:
            return Response(
                {'error': 'Email parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            keys = LicenseKey.objects.filter(
                customer_email=email
            ).select_related('brand').prefetch_related('licenses__product')
            
            if not keys.exists():
                return Response({
                    'email': email,
                    'licenses': []
                }, status=status.HTTP_200_OK)
            
            result = []
            for key in keys:
                for lic in key.licenses.all():
                    active = Activation.objects.filter(
                        license=lic,
                        is_active=True
                    ).count()
                    
                    remaining = None
                    if lic.max_seats:
                        remaining = max(0, lic.max_seats - active)
                    
                    result.append({
                        'license_key': key.key,
                        'brand': key.brand.name,
                        'product': lic.product.name,
                        'product_slug': lic.product.slug,
                        'status': lic.status,
                        'is_valid': lic.is_valid,
                        'expiration_date': lic.expiration_date,
                        'max_seats': lic.max_seats,
                        'active_seats': active,
                        'remaining_seats': remaining,
                        'created_at': lic.created_at
                    })
            
            return Response({
                'email': email,
                'total_licenses': len(result),
                'licenses': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error listing licenses by email: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to retrieve licenses'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UpdateLicenseLifecycleView(APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, license_id):
        brand = request.user
        
        try:
            lic = License.objects.select_related('license_key__brand', 'product').get(id=license_id)
        except License.DoesNotExist:
            return Response(
                {'error': 'License not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if lic.license_key.brand != brand:
            return Response(
                {'error': 'License does not belong to your brand'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = UpdateLicenseLifecycleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        
        try:
            with transaction.atomic():
                if action == 'renew':
                    exp_date = serializer.validated_data.get('expiration_date')
                    if isinstance(exp_date, str):
                        exp_date = exp_date.replace('Z', '+00:00')
                        exp_date = timezone.make_aware(datetime.fromisoformat(exp_date))
                    elif exp_date and not timezone.is_aware(exp_date):
                        exp_date = timezone.make_aware(exp_date)
                    
                    lic.expiration_date = exp_date
                    if lic.status == LicenseStatus.SUSPENDED:
                        lic.status = LicenseStatus.VALID
                    lic.save()
                    logger.info(f'Renewed {license_id} until {exp_date}')
                    
                elif action == 'suspend':
                    if lic.status == LicenseStatus.CANCELLED:
                        return Response(
                            {'error': 'Cannot suspend cancelled license'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    lic.status = LicenseStatus.SUSPENDED
                    lic.save()
                    logger.info(f'Suspended {license_id}')
                    
                elif action == 'resume':
                    if lic.status != LicenseStatus.SUSPENDED:
                        return Response(
                            {'error': 'License is not suspended'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    lic.status = LicenseStatus.VALID
                    lic.save()
                    logger.info(f'Resumed {license_id}')
                    
                elif action == 'cancel':
                    lic.status = LicenseStatus.CANCELLED
                    lic.save()
                    logger.info(f'Cancelled {license_id}')
                
                return Response({
                    'message': f'License {action}ed successfully',
                    'license': LicenseSerializer(lic).data
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f'Error updating license: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to update license'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

