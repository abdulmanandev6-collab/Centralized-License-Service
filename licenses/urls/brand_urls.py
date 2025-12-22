"""
URLs for Brand API endpoints.
"""
from django.urls import path
from licenses.views import brand_views

urlpatterns = [
    path('licenses/', brand_views.ProvisionLicenseView.as_view(), name='provision-license'),
    path('licenses/<str:license_key>/add-product/', brand_views.AddProductToLicenseKeyView.as_view(), name='add-product-to-license'),
    path('licenses/<uuid:license_id>/lifecycle/', brand_views.UpdateLicenseLifecycleView.as_view(), name='update-license-lifecycle'),
    path('licenses/by-email/', brand_views.ListLicensesByEmailView.as_view(), name='list-licenses-by-email'),
]

