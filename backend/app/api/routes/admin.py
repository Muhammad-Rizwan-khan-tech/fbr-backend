import re
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from backend.app.core.database import get_db
from backend.app.core.dependencies import require_admin_access
from backend.app.core.security import get_password_hash
from backend.app.models.base import now_utc
from backend.app.models.tenant import Organization, OrganizationSettings, OrgStatus
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.user import User, UserRole
from backend.app.models.license import License, LicenseStatus, ActivationKey, ActivationKeyStatus
from backend.app.models.device import DeviceInstallation, DeviceStatus
from backend.app.models.session import DeviceSession
from backend.app.models.fbr_credential import FBRCredential, FBRConnectionStatus
from backend.app.models.invoice import Invoice, FBRSubmissionStatus
from backend.app.models.admin_audit import AdminAuditLog
from backend.app.services.license_service import LicenseService
from backend.app.adapters.factory import FBRAdapterFactory
from backend.app.schemas.admin import (
    AdminCreateOrgRequest,
    AdminSetStatusRequest,
    AdminSetFBRCredentialsRequest,
    AdminReissueKeyRequest,
    AdminDeviceActionRequest,
    AdminStatsResponse,
    AdminAuditLogItem,
    AdminDeviceResponse,
)

router = APIRouter(prefix="/admin", tags=["Super Admin Platform API"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:50] or "org"


@router.get("/stats", response_model=AdminStatsResponse)
def get_platform_stats(
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Provides high-level platform statistics for the Super Admin dashboard."""
    total_orgs = db.query(func.count(Organization.id)).scalar() or 0
    active_orgs = db.query(func.count(Organization.id)).filter(Organization.status == OrgStatus.ACTIVE.value).scalar() or 0
    suspended_orgs = db.query(func.count(Organization.id)).filter(Organization.status == OrgStatus.SUSPENDED.value).scalar() or 0

    total_licenses = db.query(func.count(License.id)).scalar() or 0
    active_licenses = db.query(func.count(License.id)).filter(License.status == LicenseStatus.ACTIVE.value).scalar() or 0
    revoked_licenses = db.query(func.count(License.id)).filter(License.status == LicenseStatus.REVOKED.value).scalar() or 0

    total_devices = db.query(func.count(DeviceInstallation.id)).scalar() or 0
    active_devices = db.query(func.count(DeviceInstallation.id)).filter(DeviceInstallation.status == DeviceStatus.ACTIVE.value).scalar() or 0

    total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
    submitted_invoices = db.query(func.count(Invoice.id)).filter(Invoice.fbr_status == FBRSubmissionStatus.VALID.value).scalar() or 0

    fbr_healthy = db.query(func.count(FBRCredential.id)).filter(FBRCredential.status == FBRConnectionStatus.HEALTHY.value).scalar() or 0
    fbr_failed = db.query(func.count(FBRCredential.id)).filter(FBRCredential.status == FBRConnectionStatus.FAILED.value).scalar() or 0

    return {
        "total_organizations": total_orgs,
        "active_organizations": active_orgs,
        "suspended_organizations": suspended_orgs,
        "total_licenses": total_licenses,
        "active_licenses": active_licenses,
        "revoked_licenses": revoked_licenses,
        "total_devices": total_devices,
        "active_devices": active_devices,
        "total_invoices": total_invoices,
        "submitted_invoices": submitted_invoices,
        "fbr_healthy_count": fbr_healthy,
        "fbr_failed_count": fbr_failed,
    }


@router.get("/organizations")
def list_organizations(
    search: Optional[str] = Query(None, description="Search by name, NTN, or slug"),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Lists all customer organizations with license and hardware device summaries."""
    query = db.query(Organization)

    if status_filter:
        query = query.filter(Organization.status == status_filter.upper())

    if search:
        term = f"%{search.strip()}%"
        query = query.outerjoin(Taxpayer).filter(
            (Organization.name.ilike(term)) |
            (Organization.slug.ilike(term)) |
            (Taxpayer.ntn.ilike(term))
        )

    total = query.count()
    orgs = query.order_by(Organization.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for o in orgs:
        active_devices = db.query(func.count(DeviceInstallation.id)).filter(
            DeviceInstallation.organization_id == o.id,
            DeviceInstallation.status == DeviceStatus.ACTIVE.value,
        ).scalar() or 0

        latest_license = db.query(License).filter(License.organization_id == o.id).order_by(License.created_at.desc()).first()
        cred = db.query(FBRCredential).filter(FBRCredential.organization_id == o.id).first()
        invoices_count = db.query(func.count(Invoice.id)).filter(Invoice.tenant_id == o.id).scalar() or 0

        items.append({
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "status": o.status,
            "ntn": o.taxpayer.ntn if o.taxpayer else None,
            "strn": o.taxpayer.strn if o.taxpayer else None,
            "province": o.taxpayer.province if o.taxpayer else None,
            "license_id": latest_license.id if latest_license else None,
            "license_number": latest_license.license_number if latest_license else None,
            "license_status": latest_license.status if latest_license else "NONE",
            "active_devices_count": active_devices,
            "max_devices": latest_license.max_devices if latest_license else 5,
            "fbr_status": cred.status if cred else "UNCONFIGURED",
            "fbr_provider": cred.provider if cred else "MOCK",
            "invoices_count": invoices_count,
            "created_at": o.created_at.isoformat(),
        })

    return {"total": total, "items": items, "limit": limit, "offset": offset}


@router.post("/organizations")
def create_organization(
    req: AdminCreateOrgRequest,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Creates a customer organization, permanent license, and initial activation secret."""
    # Ensure slug uniqueness
    base_slug = _slugify(req.name)
    slug = base_slug
    idx = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{idx}"
        idx += 1

    org = Organization(
        name=req.name.strip(),
        slug=slug,
        status=OrgStatus.ACTIVE.value,
        is_active=True,
    )
    db.add(org)
    db.flush()

    city = getattr(req, "city", None) or "Karachi"

    # Create Taxpayer Profile
    taxpayer = Taxpayer(
        tenant_id=org.id,
        legal_name=req.name.strip(),
        trade_name=req.name.strip(),
        ntn=req.ntn.strip(),
        strn=req.strn.strip() if req.strn else None,
        province=req.province.strip(),
        city=city,
        address=req.address.strip(),
    )
    db.add(taxpayer)

    # Create default Head Office Branch
    branch = Branch(
        tenant_id=org.id,
        branch_name="Head Office",
        branch_code="HO-01",
        address=req.address.strip(),
        city=city,
        province=req.province.strip(),
        is_main=True,
        is_active=True,
        fbr_pos_id=req.fbr_pos_id,
    )
    db.add(branch)

    # Create Organization Settings
    settings_obj = OrganizationSettings(
        organization_id=org.id,
        invoice_prefix="INV",
        fbr_mode=req.fbr_environment or "DEMO",
        fbr_pos_id=req.fbr_pos_id,
    )
    db.add(settings_obj)

    # Create initial Organization Admin User
    initial_password = req.admin_password or "Secure@Pass2026!"
    user = User(
        tenant_id=org.id,
        email=req.admin_email.lower().strip(),
        full_name=req.admin_name.strip(),
        hashed_password=get_password_hash(initial_password),
        role=UserRole.ORG_ADMIN.value,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    # Create Permanent License and generate Activation Key
    license_obj, raw_activation_secret = LicenseService.create_permanent_license_for_org(
        db=db,
        organization=org,
        max_devices=req.max_devices,
        issued_by=admin,
    )

    # Configure initial FBR Credentials if provided
    cred = FBRCredential(
        organization_id=org.id,
        environment=req.fbr_environment or "DEMO",
        provider=req.fbr_provider or "MOCK",
        fbr_pos_id=req.fbr_pos_id,
        status=FBRConnectionStatus.UNTESTED.value,
    )
    cred.set_credentials(
        api_key=req.fbr_api_key,
        client_id=req.fbr_client_id,
        client_secret=req.fbr_client_secret,
        auth_token=req.fbr_auth_token,
    )
    db.add(cred)

    audit = AdminAuditLog(
        admin_identity=admin,
        action="ORGANIZATION_CREATED",
        target_type="ORGANIZATION",
        target_id=org.id,
        details=f"Created organization {org.name} (NTN: {req.ntn}) with permanent license {license_obj.license_number}",
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "organization_id": org.id,
        "organization_slug": org.slug,
        "license_id": license_obj.id,
        "license_number": license_obj.license_number,
        "one_time_activation_secret": raw_activation_secret,
        "initial_admin_email": user.email,
        "initial_admin_password": initial_password if not req.admin_password else "Configured",
        "message": "Organization created successfully. Reveal the activation key to the customer once.",
    }


@router.get("/organizations/{org_id}")
def get_organization_detail(
    org_id: str,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Returns comprehensive organization information, license, devices, and masked FBR credentials."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    license_obj = db.query(License).filter(License.organization_id == org.id).order_by(License.created_at.desc()).first()
    pending_key = None
    if license_obj:
        pending_key_obj = db.query(ActivationKey).filter(
            ActivationKey.license_id == license_obj.id,
            ActivationKey.status == ActivationKeyStatus.PENDING.value,
        ).first()
        if pending_key_obj:
            pending_key = {
                "id": pending_key_obj.id,
                "key_prefix": pending_key_obj.key_prefix,
                "status": pending_key_obj.status,
                "expires_at": pending_key_obj.expires_at.isoformat() if pending_key_obj.expires_at else None,
                "created_at": pending_key_obj.created_at.isoformat(),
            }

    devices = db.query(DeviceInstallation).filter(DeviceInstallation.organization_id == org.id).all()
    devices_data = [
        {
            "id": d.id,
            "device_name": d.device_name,
            "device_fingerprint": d.device_fingerprint[:16] + "...",
            "os_info": d.os_info,
            "app_version": d.app_version,
            "ip_address": d.ip_address,
            "status": d.status,
            "activated_at": d.activated_at.isoformat(),
            "last_seen_at": d.last_seen_at.isoformat(),
            "revoked_at": d.revoked_at.isoformat() if d.revoked_at else None,
            "revocation_reason": d.revocation_reason,
        }
        for d in devices
    ]

    cred = db.query(FBRCredential).filter(FBRCredential.organization_id == org.id).first()
    masked_cred = cred.to_masked_dict() if cred else None

    invoices_total = db.query(func.count(Invoice.id)).filter(Invoice.tenant_id == org.id).scalar() or 0
    invoices_submitted = db.query(func.count(Invoice.id)).filter(
        Invoice.tenant_id == org.id,
        Invoice.fbr_status == FBRSubmissionStatus.VALID.value,
    ).scalar() or 0

    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "status": org.status,
            "created_at": org.created_at.isoformat(),
        },
        "taxpayer": {
            "legal_name": org.taxpayer.legal_name if org.taxpayer else None,
            "ntn": org.taxpayer.ntn if org.taxpayer else None,
            "strn": org.taxpayer.strn if org.taxpayer else None,
            "province": org.taxpayer.province if org.taxpayer else None,
            "address": org.taxpayer.address if org.taxpayer else None,
        } if org.taxpayer else None,
        "license": {
            "id": license_obj.id,
            "license_number": license_obj.license_number,
            "license_type": license_obj.license_type,
            "status": license_obj.status,
            "max_devices": license_obj.max_devices,
            "issued_at": license_obj.issued_at.isoformat(),
            "revoked_at": license_obj.revoked_at.isoformat() if license_obj.revoked_at else None,
            "revocation_reason": license_obj.revocation_reason,
        } if license_obj else None,
        "pending_activation_key": pending_key,
        "fbr_credentials": masked_cred,
        "devices": devices_data,
        "stats": {
            "invoices_total": invoices_total,
            "invoices_submitted": invoices_submitted,
            "active_devices_count": sum(1 for d in devices if d.status == DeviceStatus.ACTIVE.value),
        },
    }


@router.put("/organizations/{org_id}/status")
def update_organization_status(
    org_id: str,
    req: AdminSetStatusRequest,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Suspends or restores access for a customer organization."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    new_status = req.status.upper()
    if new_status not in (OrgStatus.ACTIVE.value, OrgStatus.SUSPENDED.value):
        raise HTTPException(status_code=400, detail="Invalid status value")

    org.status = new_status
    org.is_active = (new_status == OrgStatus.ACTIVE.value)

    if new_status == OrgStatus.SUSPENDED.value:
        # Revoke all active sessions immediately
        db.query(DeviceSession).filter(DeviceSession.organization_id == org.id).update({"is_revoked": True})

    audit = AdminAuditLog(
        admin_identity=admin,
        action="ORGANIZATION_STATUS_CHANGED",
        target_type="ORGANIZATION",
        target_id=org.id,
        details=f"Status set to {new_status}. Reason: {req.reason or 'Not specified'}",
    )
    db.add(audit)
    db.commit()

    return {"success": True, "organization_id": org.id, "status": org.status}


@router.post("/organizations/{org_id}/licenses/reissue")
def reissue_organization_activation_key(
    org_id: str,
    req: AdminReissueKeyRequest,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Reissues a new one-time activation secret for the customer organization."""
    license_obj, raw_secret = LicenseService.reissue_activation_key(
        db=db,
        organization_id=org_id,
        admin_identity=admin,
        reason=req.reason,
    )
    return {
        "success": True,
        "license_id": license_obj.id,
        "license_number": license_obj.license_number,
        "one_time_activation_secret": raw_secret,
        "message": "New activation key generated. Reveal to customer once and store securely.",
    }


@router.put("/licenses/{license_id}/revoke")
def revoke_license(
    license_id: str,
    req: AdminDeviceActionRequest,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Revokes a customer's permanent license."""
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    lic.status = LicenseStatus.REVOKED.value
    lic.revoked_at = now_utc()
    lic.revoked_by = admin
    lic.revocation_reason = req.reason or "Revoked by Super Administrator"

    # Revoke sessions
    db.query(DeviceSession).filter(DeviceSession.organization_id == lic.organization_id).update({"is_revoked": True})

    audit = AdminAuditLog(
        admin_identity=admin,
        action="LICENSE_REVOKED",
        target_type="LICENSE",
        target_id=lic.id,
        details=f"License {lic.license_number} revoked. Reason: {lic.revocation_reason}",
    )
    db.add(audit)
    db.commit()

    return {"success": True, "license_id": lic.id, "status": lic.status}


@router.put("/licenses/{license_id}/restore")
def restore_license(
    license_id: str,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Restores a revoked permanent license."""
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    lic.status = LicenseStatus.ACTIVE.value
    lic.revoked_at = None
    lic.revoked_by = None
    lic.revocation_reason = None

    audit = AdminAuditLog(
        admin_identity=admin,
        action="LICENSE_RESTORED",
        target_type="LICENSE",
        target_id=lic.id,
        details=f"License {lic.license_number} restored to ACTIVE",
    )
    db.add(audit)
    db.commit()

    return {"success": True, "license_id": lic.id, "status": lic.status}


@router.put("/devices/{device_id}/revoke")
def revoke_device(
    device_id: str,
    req: AdminDeviceActionRequest,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Revokes a specific desktop device installation."""
    dev = db.query(DeviceInstallation).filter(DeviceInstallation.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    dev.status = DeviceStatus.REVOKED.value
    dev.revoked_at = now_utc()
    dev.revoked_by = admin
    dev.revocation_reason = req.reason or "Revoked by Administrator"

    # Revoke active sessions for this device
    db.query(DeviceSession).filter(DeviceSession.device_id == dev.id).update({"is_revoked": True})

    audit = AdminAuditLog(
        admin_identity=admin,
        action="DEVICE_REVOKED",
        target_type="DEVICE",
        target_id=dev.id,
        details=f"Device {dev.device_name} ({dev.device_fingerprint[:8]}...) revoked",
    )
    db.add(audit)
    db.commit()

    return {"success": True, "device_id": dev.id, "status": dev.status}


@router.post("/organizations/{org_id}/fbr-credentials")
def set_organization_fbr_credentials(
    org_id: str,
    req: AdminSetFBRCredentialsRequest,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Configures or rotates organization-specific FBR credentials (encrypted at rest)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    cred = db.query(FBRCredential).filter(FBRCredential.organization_id == org_id).first()
    if not cred:
        cred = FBRCredential(organization_id=org_id)
        db.add(cred)

    cred.environment = req.environment
    cred.provider = req.provider
    if req.fbr_pos_id is not None:
        cred.fbr_pos_id = req.fbr_pos_id
    if req.base_url is not None:
        cred.base_url = req.base_url

    cred.set_credentials(
        api_key=req.api_key,
        client_id=req.client_id,
        client_secret=req.client_secret,
        auth_token=req.auth_token,
        cert_passphrase=req.cert_passphrase,
    )
    cred.status = FBRConnectionStatus.UNTESTED.value

    # Update organization setting mode if matching
    if org.settings:
        org.settings.fbr_mode = req.environment
        if req.fbr_pos_id:
            org.settings.fbr_pos_id = req.fbr_pos_id

    audit = AdminAuditLog(
        admin_identity=admin,
        action="FBR_CREDENTIALS_UPDATED",
        target_type="ORGANIZATION",
        target_id=org.id,
        details=f"FBR credentials rotated. Env={req.environment}, Provider={req.provider}, POS={req.fbr_pos_id}",
    )
    db.add(audit)
    db.commit()

    return {"success": True, "credentials": cred.to_masked_dict()}


@router.get("/organizations/{org_id}/fbr-credentials")
def get_organization_fbr_credentials(
    org_id: str,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Returns masked FBR credential status for the organization."""
    cred = db.query(FBRCredential).filter(FBRCredential.organization_id == org_id).first()
    if not cred:
        return {"is_configured": False, "status": "NOT_CONFIGURED"}
    return {"is_configured": True, **cred.to_masked_dict()}


@router.post("/organizations/{org_id}/fbr-test-connection")
def test_organization_fbr_connection(
    org_id: str,
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Verifies and tests the FBR connection with the organization's configured credentials."""
    cred = db.query(FBRCredential).filter(FBRCredential.organization_id == org_id).first()
    if not cred:
        raise HTTPException(status_code=400, detail="No FBR credentials configured for this organization.")

    adapter = FBRAdapterFactory.get_adapter_for_tenant(cred)
    test_result = adapter.test_connection()

    cred.last_tested_at = now_utc()
    if test_result.get("success"):
        cred.status = FBRConnectionStatus.HEALTHY.value
        cred.last_success_at = now_utc()
        cred.last_error = None
    else:
        cred.status = FBRConnectionStatus.FAILED.value
        cred.last_error = test_result.get("message", "Connection test failed")

    db.commit()

    return {
        "success": test_result.get("success", False),
        "status": cred.status,
        "message": test_result.get("message"),
        "latency_ms": test_result.get("latency_ms"),
    }


@router.get("/audit-logs")
def list_admin_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Returns the administrative action audit trail."""
    query = db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "admin_identity": log.admin_identity,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in items
        ],
        "limit": limit,
        "offset": offset,
    }
