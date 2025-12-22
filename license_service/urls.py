"""
URL configuration for license_service project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/brand/', include('licenses.urls.brand_urls')),
    path('api/product/', include('licenses.urls.product_urls')),
    path('api/health/', include('licenses.urls.health_urls')),
]

