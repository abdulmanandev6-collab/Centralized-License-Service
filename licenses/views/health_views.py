"""
Health check endpoints for observability.
"""

from django.db import connection
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """
    Health check endpoint to verify service is operational.
    """

    permission_classes = []
    authentication_classes = []

    @swagger_auto_schema(
        operation_summary="Health Check",
        operation_description="Check service health and database connection",
        tags=["Z. Health Check"],
        responses={
            200: "Success",
            503: "Service unavailable",
        },
    )
    def get(self, request):
        try:
            # Check database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            return Response(
                {
                    "status": "healthy",
                    "database": "connected",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {
                    "status": "unhealthy",
                    "database": "disconnected",
                    "error": str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
