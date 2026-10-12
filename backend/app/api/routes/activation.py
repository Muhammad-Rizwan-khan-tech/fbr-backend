import hashlib
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.models.fbr_credential import FBRCredential
from backend.app.models.session import DeviceSession
from backend.app.services.license_service import LicenseService
from backend.app.schemas.license import (
    ActivationRedeemRequest,
    ActivationRedeemResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    LicenseStatusResponse,
    FBRConnectionPublicStatusResponse,
)

router = APIRouter(tags=["Desktop Activation & Licensing"])


@router.post("/activation/redeem", response_model=ActivationRedeemResponse)
def redeem_activation_key(
    req: ActivationRedeemRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Redeems an admin-generated activation secret on the desktop client.
    
    Binds the desktop device hardware fingerprint to the organization and permanent license,
    returning an access token and refresh token.
    """
    client_ip = request.client.host if request.client else None
    result = LicenseService.redeem_activation_key(
        db=db,
        activation_key=req.activation_key,
        device_fingerprint=req.device_fingerprint,
        device_name=req.device_name or "Windows Terminal",
        os_info=req.os_info or "Windows",
        app_version=req.app_version or "1.0.0",
        ip_address=client_ip,
    )
    return {
        "success": True,
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
        "expires_in": result["expires_in"],
        "license": result["license"],
        "organization": result["organization"],
        "device_id": result["device_id"],
    }


@router.post("/auth/refresh", response_model=TokenRefreshResponse)
def refresh_session(
    req: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """Refreshes an existing desktop session token after verifying device validity and license status."""
    result = LicenseService.refresh_session(
        db=db,
        refresh_token=req.refresh_token,
        device_fingerprint=req.device_fingerprint,
    )
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
        "expires_in": result["expires_in"],
    }


@router.post("/auth/logout")
def logout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revokes active refresh token sessions for the current device."""
    # Revoke sessions for this user and tenant
    db.query(DeviceSession).filter(
        DeviceSession.user_id == current_user.id,
        DeviceSession.organization_id == current_user.tenant_id,
    ).update({"is_revoked": True})
    db.commit()
    return {"success": True, "message": "Successfully logged out from device."}


@router.get("/me")
def get_current_principal_profile(
    current_user: User = Depends(get_current_user),
    tenant: Organization = Depends(get_current_tenant),
):
    """Returns the authenticated principal and tenant organization context."""
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "phone": current_user.phone,
        },
        "organization": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
            "plan": tenant.plan,
        },
    }


@router.get("/license/status", response_model=LicenseStatusResponse)
def get_license_status(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Validates the organization's permanent license status in real-time."""
    return LicenseService.get_license_status(db, tenant.id)


@router.get("/organizations/current")
def get_current_organization(
    tenant: Organization = Depends(get_current_tenant),
):
    """Returns public profile, taxpayer info, and branches for the authenticated tenant."""
    taxpayer_data = None
    if tenant.taxpayer:
        taxpayer_data = {
            "ntn": tenant.taxpayer.ntn,
            "strn": tenant.taxpayer.strn,
            "legal_name": tenant.taxpayer.legal_name,
            "business_name": tenant.taxpayer.business_name,
            "province": tenant.taxpayer.province,
            "address": tenant.taxpayer.address,
            "city": tenant.taxpayer.city,
        }

    branches_data = [
        {
            "id": b.id,
            "name": b.name,
            "code": b.code,
            "address": b.address,
            "is_head_office": b.is_head_office,
            "is_active": b.is_active,
        }
        for b in (tenant.branches or [])
    ]

    settings_data = {
        "invoice_prefix": tenant.settings.invoice_prefix if tenant.settings else "INV",
        "fbr_mode": tenant.settings.fbr_mode if tenant.settings else "DEMO",
    }

    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "taxpayer": taxpayer_data,
        "branches": branches_data,
        "settings": settings_data,
    }


@router.get("/fbr/connection/status", response_model=FBRConnectionPublicStatusResponse)
def get_fbr_connection_status(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Returns organization-specific FBR connection health and masked configuration."""
    cred = db.query(FBRCredential).filter(FBRCredential.organization_id == tenant.id).first()
    if not cred:
        fbr_mode = tenant.settings.fbr_mode if tenant.settings else "DEMO"
        return {
            "is_configured": False,
            "environment": fbr_mode,
            "provider": "MOCK",
            "status": "UNTESTED",
            "fbr_pos_id": tenant.settings.fbr_pos_id if tenant.settings else None,
            "masked_api_key": None,
            "last_tested_at": None,
            "last_success_at": None,
            "last_error": None,
        }

    masked = cred.to_masked_dict()
    return {
        "is_configured": cred.is_active,
        "environment": cred.environment,
        "provider": cred.provider,
        "status": cred.status,
        "fbr_pos_id": cred.fbr_pos_id,
        "masked_api_key": masked.get("masked_api_key"),
        "last_tested_at": cred.last_tested_at,
        "last_success_at": cred.last_success_at,
        "last_error": cred.last_error,
    }
