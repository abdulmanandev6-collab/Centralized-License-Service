"""
Views for Product API endpoints.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


class ActivateLicenseView(APIView):
    """
    US3: End-user product can activate a license
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Implementation will be added in US3
        return Response({'message': 'To be implemented'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class CheckLicenseStatusView(APIView):
    """
    US4: User can check license status
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Implementation will be added in US4
        return Response({'message': 'To be implemented'}, status=status.HTTP_501_NOT_IMPLEMENTED)

