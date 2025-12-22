"""
Views for Product API endpoints.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from licenses.models import LicenseKey, License, Activation
from licenses.serializers import ActivateLicenseRequestSerializer
import logging

logger = logging.getLogger(__name__)


class ActivateLicenseView(APIView):
    permission_classes = [IsAuthenticated]
    
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
    """
    US4: User can check license status
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Implementation will be added in US4
        return Response({'message': 'To be implemented'}, status=status.HTTP_501_NOT_IMPLEMENTED)

