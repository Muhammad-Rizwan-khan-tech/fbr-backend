from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import decode_access_token
from backend.app.models.user import User, UserRole
from backend.app.models.tenant import Organization

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    tenant_id: str = payload.get("tenant_id")
    if not user_id or not tenant_id:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    
    return user


def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Organization:
    tenant = db.query(Organization).filter(Organization.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant organization not found")
    if not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive or suspended")
    return tenant


def require_roles(*allowed_roles: str):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == UserRole.SUPER_ADMIN.value:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {allowed_roles}"
            )
        return current_user
    return role_checker


# ---------------------------------------------------------------------------------
# Developer API Key Authentication
# ---------------------------------------------------------------------------------
from fastapi import Request
from backend.app.models.api_key import ApiKey
from backend.app.core.security import hash_api_key
from backend.app.core.redis_client import rate_limit_allow
from backend.app.core.context import execution_context
from backend.app.models.base import now_utc


class ApiKeyAuth:
    def __init__(self, key: ApiKey, tenant: Organization):
        self.key = key
        self.tenant = tenant

    @property
    def api_key(self) -> ApiKey:
        return self.key


def require_api_key(required_scope: Optional[str] = None):
    """FastAPI dependency for authenticating requests with an external API key (X-API-Key)."""
    def api_key_checker(
        request: Request,
        db: Session = Depends(get_db),
    ) -> ApiKeyAuth:
        raw_key = request.headers.get("X-API-Key")
        if not raw_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer fbr_"):
                raw_key = auth_header.split(" ", 1)[1]

        if not raw_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key required. Provide 'X-API-Key' header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        hashed = hash_api_key(raw_key)
        api_key_record = db.query(ApiKey).filter(
            ApiKey.hashed_key == hashed,
            ApiKey.is_active == True
        ).first()

        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key."
            )

        # Check expiration
        if api_key_record.expires_at and api_key_record.expires_at < now_utc():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired."
            )

        # Check scopes
        if required_scope:
            allowed_scopes = [s.strip() for s in api_key_record.scopes.split(",") if s.strip()]
            if "*" not in allowed_scopes and required_scope not in allowed_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API key lacks required scope '{required_scope}'. Granted: {allowed_scopes}"
                )

        # Enforce rate limit per API key
        if not rate_limit_allow(
            scope="api_key",
            identity=api_key_record.id,
            limit=api_key_record.rate_limit_per_minute,
            window_seconds=60
        ):
            from backend.app.core.errors import RateLimitError
            raise RateLimitError(
                message=f"API Key rate limit exceeded: max {api_key_record.rate_limit_per_minute} req/min.",
                status_code=429
            )

        # Retrieve and verify tenant
        tenant = db.query(Organization).filter(Organization.id == api_key_record.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization associated with this API key is inactive or suspended."
            )

        # Set tenant context
        execution_context.tenant_id.set(tenant.id)

        # Update last used timestamp
        try:
            api_key_record.last_used_at = now_utc()
            db.commit()
        except Exception:
            db.rollback()

        return ApiKeyAuth(key=api_key_record, tenant=tenant)

    return api_key_checker

