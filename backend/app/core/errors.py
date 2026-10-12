"""Standardized application errors.

All API errors are rendered as::

    {"success": false,
     "error": {"code": "FBR_TIMEOUT", "message": "...", "correlation_id": "..."},
     "detail": "..."}            # legacy key kept for backwards compatibility
"""
from typing import Any, Dict, Optional


class AppError(Exception):
    code = "INTERNAL_ERROR"
    status_code = 500
    default_message = "An unexpected error occurred."

    def __init__(self, message: Optional[str] = None, *, details: Optional[Dict[str, Any]] = None,
                 status_code: Optional[int] = None):
        self.message = message or self.default_message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class ValidationAppError(AppError):
    code, status_code, default_message = "VALIDATION_ERROR", 422, "The request is invalid."


class AuthenticationError(AppError):
    code, status_code, default_message = "AUTHENTICATION_ERROR", 401, "Authentication is required."


class AuthorizationError(AppError):
    code, status_code, default_message = "AUTHORIZATION_ERROR", 403, "You are not allowed to perform this action."


class TenantAccessError(AppError):
    code, status_code, default_message = "TENANT_ACCESS_ERROR", 403, "Resource does not belong to your organization."


class NotFoundError(AppError):
    code, status_code, default_message = "NOT_FOUND", 404, "Resource not found."


class ConflictError(AppError):
    code, status_code, default_message = "CONFLICT", 409, "The request conflicts with the current resource state."


class RateLimitError(AppError):
    code, status_code, default_message = "RATE_LIMITED", 429, "Too many requests. Please retry later."


class InvoiceInvalidError(AppError):
    code, status_code, default_message = "INVOICE_INVALID", 422, "Invoice failed validation."


class TaxCalculationAppError(AppError):
    code, status_code, default_message = "TAX_CALCULATION_ERROR", 422, "Tax calculation failed."


class FBRValidationError(AppError):
    code, status_code, default_message = "FBR_VALIDATION_ERROR", 422, "FBR rejected the invoice data."


class FBRTimeoutError(AppError):
    code, status_code, default_message = "FBR_TIMEOUT", 504, "FBR submission timed out."


class FBRRejectedError(AppError):
    code, status_code, default_message = "FBR_REJECTED", 422, "FBR rejected the invoice."


class FBRUnavailableError(AppError):
    code, status_code, default_message = "FBR_UNAVAILABLE", 503, "FBR service is unavailable."


class FBRNotConfiguredError(AppError):
    code, status_code, default_message = "FBR_NOT_CONFIGURED", 409, "The selected FBR integration is not configured."


class PDFGenerationError(AppError):
    code, status_code, default_message = "PDF_GENERATION_ERROR", 500, "PDF generation failed."


class StorageError(AppError):
    code, status_code, default_message = "STORAGE_ERROR", 502, "Document storage operation failed."


class QueueError(AppError):
    code, status_code, default_message = "QUEUE_ERROR", 503, "Background queue is unavailable."


STATUS_TO_CODE = {
    400: "VALIDATION_ERROR",
    401: "AUTHENTICATION_ERROR",
    403: "AUTHORIZATION_ERROR",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def error_body(code: str, message: str, correlation_id: Optional[str], details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message, "correlation_id": correlation_id}
    if details:
        error["details"] = details
    return {"success": False, "error": error, "detail": message}
