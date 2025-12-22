"""
Views for Product API endpoints.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from licenses.models import LicenseKey, License, Activation
from licenses.serializers import ActivateLicenseRequestSerializer, DeactivateSeatRequestSerializer
import logging

logger = logging.getLogger(__name__)


class ActivateLicenseView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary='US 3: Activate License',
        operation_description='Activates the license for a specific site or instance. Uses up a seat if there\'s a limit.\n\n**What is instance_id?**\n- Your website URL (e.g., https://mysite.com)\n- Your domain name (e.g., mysite.com)\n- A machine/device ID (e.g., machine-12345)\n\n**What is product_slug?**\n- The product identifier from your license (e.g., "rankmath", "wprocket")\n- Check your license status endpoint to see available products',
        tags=['US 3: License Activation'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['instance_id', 'product_slug'],
            properties={
                'instance_id': openapi.Schema(type=openapi.TYPE_STRING, description='Your site URL, domain, or machine ID where the product is installed (e.g., https://mysite.com, mysite.com, or machine-12345)', example='https://mysite.com'),
                'product_slug': openapi.Schema(type=openapi.TYPE_STRING, description='Product slug from your license (e.g., rankmath, wprocket). Check your license status to see available products.', example='rankmath'),
            },
            example={
                'instance_id': 'https://mysite.com',
                'product_slug': 'rankmath'
            }
        ),
        responses={
            201: 'Success',
            200: 'Success',
            400: 'Bad request',
            403: 'Forbidden',
            404: 'Not found',
        },
        security=[{'X-License-Key': []}],
        operation_id='product_activate_create'
    )
    def post(self, request):
        lk = request.user
        
        serializer = ActivateLicenseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        instance_id = serializer.validated_data['instance_id']
        product_slug = serializer.validated_data['product_slug']
        
        try:
            license_obj = License.objects.filter(
                license_key=lk,
                product__slug=product_slug,
                product__is_active=True
            ).first()
            
            if not license_obj:
                return Response(
                    {'error': f'License for "{product_slug}" not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not license_obj.is_valid:
                return Response(
                    {'error': f'License is {license_obj.status} or expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                existing = Activation.objects.filter(
                    license=license_obj,
                    instance_id=instance_id,
                    is_active=True
                ).first()
                
                if existing:
                    return Response({
                        'status': 'success',
                        'message': 'Already activated for this instance',
                        'activation_id': str(existing.id),
                        'instance_id': existing.instance_id,
                        'activated_at': existing.activated_at
                    }, status=status.HTTP_200_OK)
                
                active_count = Activation.objects.filter(
                    license=license_obj,
                    is_active=True
                ).count()
                
                if license_obj.max_seats and active_count >= license_obj.max_seats:
                    return Response(
                        {'error': f'Seat limit reached ({license_obj.max_seats} seats)'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                activation = Activation.objects.create(
                    license=license_obj,
                    instance_id=instance_id,
                    is_active=True
                )
                
                logger.info(f'Activated {license_obj.id} for {instance_id}')
                
                remaining = None
                if license_obj.max_seats:
                    remaining = license_obj.max_seats - active_count - 1
                
                return Response({
                    'status': 'success',
                    'message': 'License activated successfully',
                    'activation_id': str(activation.id),
                    'instance_id': activation.instance_id,
                    'product': license_obj.product.name,
                    'activated_at': activation.activated_at,
                    'remaining_seats': remaining
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f'Error activating license: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to activate license'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CheckLicenseStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary='US 4: Check License Status',
        operation_description='See what licenses you have, their status, and how many seats are left.',
        tags=['US 4: License Status Check'],
        responses={
            200: 'Success',
            403: 'Invalid license key',
        },
        security=[{'X-License-Key': []}],
        operation_id='product_check_list'
    )
    def get(self, request):
        lk = request.user
        
        try:
            licenses = License.objects.filter(license_key=lk).select_related('product')
            
            licenses_data = []
            for lic in licenses:
                active_count = Activation.objects.filter(
                    license=lic,
                    is_active=True
                ).count()
                
                remaining = None
                if lic.max_seats is not None:
                    remaining = max(0, lic.max_seats - active_count)
                
                licenses_data.append({
                    'product': lic.product.name,
                    'product_slug': lic.product.slug,
                    'status': lic.status,
                    'is_valid': lic.is_valid,
                    'expiration_date': lic.expiration_date,
                    'max_seats': lic.max_seats,
                    'active_seats': active_count,
                    'remaining_seats': remaining
                })
            
            return Response({
                'license_key': lk.key,
                'customer_email': lk.customer_email,
                'brand': lk.brand.name,
                'licenses': licenses_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error checking license status: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to check license status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeactivateSeatView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary='US 5: Deactivate Seat',
        operation_description='Deactivate an activation to free up a seat. Useful when moving to a new site.',
        tags=['US 5: Seat Deactivation'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['instance_id', 'product_slug'],
            properties={
                'instance_id': openapi.Schema(type=openapi.TYPE_STRING, description='The instance to deactivate', example='https://oldsite.com'),
                'product_slug': openapi.Schema(type=openapi.TYPE_STRING, description='Product slug', example='rankmath'),
            },
            example={
                'instance_id': 'https://oldsite.com',
                'product_slug': 'rankmath'
            }
        ),
        responses={
            200: 'Success',
            404: 'Not found',
        },
        security=[{'X-License-Key': []}],
        operation_id='product_deactivate_create'
    )
    def post(self, request):
        lk = request.user
        
        serializer = DeactivateSeatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        instance_id = serializer.validated_data['instance_id']
        product_slug = serializer.validated_data['product_slug']
        
        try:
            lic = License.objects.filter(
                license_key=lk,
                product__slug=product_slug,
                product__is_active=True
            ).first()
            
            if not lic:
                return Response(
                    {'error': f'License for "{product_slug}" not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            with transaction.atomic():
                act = Activation.objects.filter(
                    license=lic,
                    instance_id=instance_id,
                    is_active=True
                ).first()
                
                if not act:
                    return Response(
                        {'error': 'No active activation found for this instance'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                Activation.objects.filter(id=act.id).update(
                    is_active=False,
                    deactivated_at=timezone.now()
                )
                
                active = Activation.objects.filter(
                    license=lic,
                    is_active=True
                ).count()
                
                remaining = None
                if lic.max_seats:
                    remaining = lic.max_seats - active
                
                logger.info(f'Deactivated {instance_id} for {lic.id}')
                
                return Response({
                    'status': 'success',
                    'message': 'Seat deactivated successfully',
                    'instance_id': instance_id,
                    'product': lic.product.name,
                    'deactivated_at': timezone.now(),
                    'remaining_seats': remaining
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f'Error deactivating seat: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to deactivate seat'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

