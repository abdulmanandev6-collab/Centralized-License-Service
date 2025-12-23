"""
Custom permission classes for the License Service.
"""

from rest_framework import permissions


class BrandAPIPermission(permissions.BasePermission):
    """
    Permission class for Brand API endpoints.
    Checks if request.user is a Brand object (set by BrandAPIAuthentication).
    """

    def has_permission(self, request, view):
        return (
            hasattr(request, "user")
            and request.user is not None
            and isinstance(request.user, type(request.user))
            and hasattr(request.user, "api_key")
        )


class LicenseKeyPermission(permissions.BasePermission):
    """
    Permission class for Product API endpoints.
    Checks if request.user is a LicenseKey object (set by LicenseKeyAuthentication).
    """

    def has_permission(self, request, view):
        return (
            hasattr(request, "user") and request.user is not None and hasattr(request.user, "key")
        )
