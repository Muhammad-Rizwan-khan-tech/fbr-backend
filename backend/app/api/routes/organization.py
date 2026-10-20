from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.fbr_credential import FBRCredential
from backend.app.models.taxpayer import Taxpayer
from backend.app.schemas.tenant import (
    OrganizationResponse, OrganizationSettingsUpdate, OrganizationSettingsResponse,
    TaxpayerUpdate, TaxpayerResponse
)
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/organization", tags=["Organization"])


@router.get("", response_model=OrganizationResponse)
def get_organization_profile(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    return tenant


@router.patch("/settings", response_model=OrganizationSettingsResponse)
def update_settings(
    data: OrganizationSettingsUpdate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value)),
    db: Session = Depends(get_db)
):
    settings = db.query(OrganizationSettings).filter(
        OrganizationSettings.organization_id == tenant.id
    ).first()
    if not settings:
        settings = OrganizationSettings(organization_id=tenant.id)
        db.add(settings)

    values = data.model_dump(exclude_unset=True)
    new_token = values.pop("fbr_api_token", None)
    previous_mode = settings.fbr_mode
    for field, val in values.items():
        setattr(settings, field, val)
    settings.fbr_api_token = None  # Never store raw PRAL tokens in organization settings.

    cred = db.query(FBRCredential).filter(
        FBRCredential.organization_id == tenant.id
    ).first()
    if new_token and new_token.strip():
        if not cred:
            cred = FBRCredential(organization_id=tenant.id)
            db.add(cred)
        cred.set_credentials(auth_token=new_token, api_key=new_token)
        cred.is_active = True
        cred.status = "CONFIGURED_NOT_VERIFIED"
        cred.last_success_at = None
        cred.last_tested_at = None
    if cred and (new_token or previous_mode != settings.fbr_mode):
        cred.environment = settings.fbr_mode
        cred.provider = settings.fbr_mode
        cred.status = "CONFIGURED_NOT_VERIFIED"
        cred.last_success_at = None
        cred.last_tested_at = None
        cred.base_url = settings.fbr_base_url or None
        cred.fbr_pos_id = settings.fbr_pos_id or None

    db.commit()
    db.refresh(settings)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="UPDATE_SETTINGS",
        entity="OrganizationSettings",
        entity_id=settings.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={**values, "fbr_token_rotated": bool(new_token)}
    )

    return settings


@router.patch("/taxpayer", response_model=TaxpayerResponse)
def update_taxpayer(
    data: TaxpayerUpdate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.TAX_OFFICER.value)),
    db: Session = Depends(get_db)
):
    taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant.id).first()
    if not taxpayer:
        raise HTTPException(status_code=404, detail="Taxpayer profile not found")

    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(taxpayer, field, val)

    db.commit()
    db.refresh(taxpayer)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="UPDATE_TAXPAYER",
        entity="Taxpayer",
        entity_id=taxpayer.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state=data.model_dump(exclude_unset=True)
    )

    return taxpayer
