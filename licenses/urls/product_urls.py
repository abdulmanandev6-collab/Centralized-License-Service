"""
URLs for Product API endpoints.
"""
from django.urls import path
from licenses.views import product_views

urlpatterns = [
    path('activate/', product_views.ActivateLicenseView.as_view(), name='activate-license'),
    path('check/', product_views.CheckLicenseStatusView.as_view(), name='check-license-status'),
]

