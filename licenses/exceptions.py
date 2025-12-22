"""
Custom exception handlers for the License Service.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses
    and logs errors for observability.
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'error': {
                'message': str(exc),
                'code': response.status_code,
            }
        }
        
        # Add field errors if available
        if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
            custom_response_data['error']['details'] = exc.detail
        
        response.data = custom_response_data
        
        # Log error
        logger.error(
            f"API Error: {exc.__class__.__name__} - {str(exc)}",
            extra={'status_code': response.status_code, 'context': context}
        )
    else:
        # Handle unexpected errors
        logger.exception(f"Unhandled exception: {exc}")
        custom_response_data = {
            'error': {
                'message': 'An unexpected error occurred',
                'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
        }
        response = Response(custom_response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response

