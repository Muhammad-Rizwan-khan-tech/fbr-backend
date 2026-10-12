import time
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from backend.app.core.config import settings
from backend.app.core.redis_client import rate_limit_allow
from backend.app.core.errors import RateLimitError


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects production-grade HTTP security headers onto every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # Essential security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # In staging/production, enforce strict transport security
        if settings.APP_ENV in ("staging", "production") or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Content-Security-Policy (allows self and data URIs for QR images)
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data: blob:; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )

        return response


def get_client_ip(request: Request) -> str:
    """Extract client IP, inspecting X-Forwarded-For if behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(
    request: Request,
    scope: str,
    limit: int,
    window_seconds: int = 60,
    identity_override: Optional[str] = None
) -> None:
    """Enforces rate limiting based on client IP or identity override.
    
    Raises RateLimitError if limit is exceeded.
    """
    if not settings.RATE_LIMIT_ENABLED or limit <= 0:
        return

    identity = identity_override or get_client_ip(request)
    allowed = rate_limit_allow(
        scope=scope,
        identity=identity,
        limit=limit,
        window_seconds=window_seconds
    )

    if not allowed:
        raise RateLimitError(
            message=f"Rate limit exceeded: maximum {limit} requests per {window_seconds} seconds.",
            details={"scope": scope, "retry_after_seconds": window_seconds},
            status_code=429
        )


def rate_limit(scope: str, limit: int, window_seconds: int = 60):
    """FastAPI dependency factory for endpoint-level rate limiting."""
    def dependency(request: Request):
        check_rate_limit(request, scope=scope, limit=limit, window_seconds=window_seconds)
    return dependency
