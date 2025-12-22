"""
URL configuration for license_service project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
   openapi.Info(
      title="Centralized License Service API",
      default_version='v1',
      description="License management service for group.one brands. Handles provisioning, activation, and lifecycle management across multiple products.\n\n**Test Credentials:**\n- RankMath API Key: `rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w`\n- WP Rocket API Key: `wprocket-api-key-T3nmHuBuh30dT5zP872JWw`\n- Test License Key: `GHX6-889J-WUIE-02R2`\n\nUse **X-API-Key** header for Brand endpoints and **X-License-Key** header for Product endpoints.",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/brand/', include('licenses.urls.brand_urls')),
    path('api/product/', include('licenses.urls.product_urls')),
    path('api/health/', include('licenses.urls.health_urls')),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    re_path(r'^docs/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui-old'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

