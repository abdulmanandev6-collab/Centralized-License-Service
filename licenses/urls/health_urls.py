"""
URLs for health check endpoints.
"""
from django.urls import path
from licenses.views import health_views

urlpatterns = [
    path('', health_views.HealthCheckView.as_view(), name='health-check'),
]

