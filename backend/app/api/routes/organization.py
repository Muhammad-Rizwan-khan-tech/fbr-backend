from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.tenant import Organization, OrganizationSettings
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

    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(settings, field, val)

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
        after_state=data.model_dump(exclude_unset=True)
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
