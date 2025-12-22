"""
Authentication classes for Brand API and Product API.
"""
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Brand, LicenseKey


class BrandAPIAuthentication(authentication.BaseAuthentication):
    """
    Authentication for Brand API using API key.
    Brand systems use this to provision and manage licenses.
    """
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY') or request.META.get('X_API_KEY')
        
        if not api_key:
            return None
        
        try:
            brand = Brand.objects.get(api_key=api_key, is_active=True)
        except Brand.DoesNotExist:
            raise AuthenticationFailed('Invalid API key')
        
        return (brand, None)


class LicenseKeyAuthentication(authentication.BaseAuthentication):
    """
    Authentication for Product API using license key.
    End-user products use this to activate and validate licenses.
    """
    def authenticate(self, request):
        license_key = request.META.get('HTTP_X_LICENSE_KEY') or request.META.get('X_LICENSE_KEY')
        
        if not license_key:
            return None
        
        try:
            license_key_obj = LicenseKey.objects.get(key=license_key)
        except LicenseKey.DoesNotExist:
            raise AuthenticationFailed('Invalid license key')
        
        return (license_key_obj, None)

