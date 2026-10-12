from typing import List
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.tenant import Organization
from backend.app.models.api_key import ApiKey
from backend.app.models.base import now_utc
from backend.app.core.security import generate_api_key
from backend.app.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/developer/keys", tags=["Developer API"])


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    data: ApiKeyCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """Generate a new developer API key for external ERP integration.
    
    The plaintext API key is returned ONCE. Store it securely.
    """
    raw_key, key_prefix, hashed_key = generate_api_key(data.environment)
    
    expires_at = None
    if data.expires_in_days:
        expires_at = now_utc() + timedelta(days=data.expires_in_days)

    scopes_str = ",".join(data.scopes) if data.scopes else "invoices:read,invoices:write"

    api_key = ApiKey(
        tenant_id=tenant.id,
        name=data.name,
        key_prefix=key_prefix,
        hashed_key=hashed_key,
        environment=data.environment.upper(),
        scopes=scopes_str,
        rate_limit_per_minute=data.rate_limit_per_minute,
        is_active=True,
        expires_at=expires_at,
        created_by=current_user.id
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="CREATE_API_KEY",
        entity="ApiKey",
        entity_id=api_key.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={"name": api_key.name, "prefix": key_prefix, "env": api_key.environment}
    )

    response_dict = {
        "id": api_key.id,
        "tenant_id": api_key.tenant_id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "environment": api_key.environment,
        "scopes": api_key.scopes,
        "rate_limit_per_minute": api_key.rate_limit_per_minute,
        "is_active": api_key.is_active,
        "last_used_at": api_key.last_used_at,
        "expires_at": api_key.expires_at,
        "created_at": api_key.created_at,
        "raw_api_key": raw_key,
    }
    return response_dict


@router.get("", response_model=List[ApiKeyResponse])
def list_api_keys(
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """List all API keys for the current organization."""
    return db.query(ApiKey).filter(ApiKey.tenant_id == tenant.id).order_by(ApiKey.created_at.desc()).all()


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """Revoke and deactivate an API key immediately."""
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.tenant_id == tenant.id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    db.commit()

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="REVOKE_API_KEY",
        entity="ApiKey",
        entity_id=api_key.id,
        user_id=current_user.id,
        user_email=current_user.email
    )
    return None


@router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
def rotate_api_key(
    key_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """Revoke existing key and issue a new key with identical configuration."""
    old_key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.tenant_id == tenant.id).first()
    if not old_key:
        raise HTTPException(status_code=404, detail="API key not found")

    old_key.is_active = False

    raw_key, key_prefix, hashed_key = generate_api_key(old_key.environment)
    new_key = ApiKey(
        tenant_id=tenant.id,
        name=f"{old_key.name} (Rotated)",
        key_prefix=key_prefix,
        hashed_key=hashed_key,
        environment=old_key.environment,
        scopes=old_key.scopes,
        rate_limit_per_minute=old_key.rate_limit_per_minute,
        is_active=True,
        expires_at=old_key.expires_at,
        created_by=current_user.id
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="ROTATE_API_KEY",
        entity="ApiKey",
        entity_id=new_key.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={"old_key_id": old_key.id, "new_key_id": new_key.id}
    )

    return {
        "id": new_key.id,
        "tenant_id": new_key.tenant_id,
        "name": new_key.name,
        "key_prefix": new_key.key_prefix,
        "environment": new_key.environment,
        "scopes": new_key.scopes,
        "rate_limit_per_minute": new_key.rate_limit_per_minute,
        "is_active": new_key.is_active,
        "last_used_at": new_key.last_used_at,
        "expires_at": new_key.expires_at,
        "created_at": new_key.created_at,
        "raw_api_key": raw_key,
    }
