from backend.app.core.fbr_connection import connection_status
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.user import User
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.fbr_credential import FBRCredential
from backend.app.models.fbr import FBRSubmission, FBRSubmissionAttempt
from backend.app.models.invoice import Invoice
from backend.app.schemas.fbr import (
    FBRSubmissionResponse, FBRStatusResponse, FBRTestConnectionResponse
)
from backend.app.services.fbr_service import FBRService
from backend.app.adapters.factory import FBRAdapterFactory
from backend.app.services.fbr_verification_service import check_fbr_token
from backend.app.core.config import settings as app_settings

router = APIRouter(prefix="/fbr", tags=["FBR Submission Center"])


@router.get("/status", response_model=FBRStatusResponse)
def get_fbr_status(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    settings = db.query(OrganizationSettings).filter(
        OrganizationSettings.organization_id == tenant.id
    ).first()
    fbr_mode = settings.fbr_mode if settings else "DEMO"

    cred = db.query(FBRCredential).filter(FBRCredential.organization_id == tenant.id).first()
    conn_status = connection_status(cred, fbr_mode)
    is_connected = conn_status == "VERIFIED"
    last_tested_at = cred.last_tested_at if cred else None
    last_success_at = cred.last_success_at if cred else None
    last_error = cred.last_error if cred else None

    last_sub = db.query(FBRSubmission).join(Invoice, FBRSubmission.invoice_id == Invoice.id).filter(
        Invoice.status != "DELETED",
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status == "VALID"
    ).order_by(FBRSubmission.submitted_at.desc()).first()

    pending_count = db.query(FBRSubmission).join(Invoice, FBRSubmission.invoice_id == Invoice.id).filter(
        Invoice.status != "DELETED",
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status == "PENDING"
    ).count()

    failed_count = db.query(FBRSubmission).join(Invoice, FBRSubmission.invoice_id == Invoice.id).filter(
        Invoice.status != "DELETED",
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status.in_(["FAILED", "INVALID"])
    ).count()

    valid_count = db.query(FBRSubmission).join(Invoice, FBRSubmission.invoice_id == Invoice.id).filter(
        Invoice.status != "DELETED",
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status == "VALID"
    ).count()

    adapter_name = {
        "DEMO": "MockFBRAdapter",
        "MOCK": "MockFBRAdapter",
        "SANDBOX": "SandboxFBRAdapter",
        "PRODUCTION": "ProductionFBRAdapter",
    }.get((fbr_mode or "DEMO").upper(), "Unknown")

    return FBRStatusResponse(
        is_connected=is_connected,
        connection_status=conn_status,
        environment=fbr_mode,
        adapter=adapter_name,
        last_tested_at=last_tested_at,
        last_success_at=last_success_at,
        last_error=last_error,
        last_successful_submission=last_sub.submitted_at if last_sub else None,
        pending_queue_count=pending_count,
        failed_submissions_count=failed_count,
        total_valid_submissions=valid_count
    )


@router.get("/submissions", response_model=List[FBRSubmissionResponse])
def list_submissions(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    from backend.app.models.invoice import Invoice
    query = db.query(FBRSubmission).join(Invoice, FBRSubmission.invoice_id == Invoice.id).filter(FBRSubmission.tenant_id == tenant.id, Invoice.status != "DELETED")
    if status:
        query = query.filter(FBRSubmission.status == status.upper())
    return query.order_by(FBRSubmission.submitted_at.desc()).limit(limit).all()


@router.get("/submissions/{submission_id}", response_model=FBRSubmissionResponse)
def get_submission_detail(
    submission_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    sub = db.query(FBRSubmission).join(Invoice, FBRSubmission.invoice_id == Invoice.id).filter(
        Invoice.status != "DELETED",
        FBRSubmission.id == submission_id,
        FBRSubmission.tenant_id == tenant.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@router.post("/submissions/{submission_id}/retry", response_model=FBRSubmissionResponse)
def retry_submission(
    submission_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = db.query(FBRSubmission).join(Invoice, FBRSubmission.invoice_id == Invoice.id).filter(
        Invoice.status != "DELETED",
        FBRSubmission.id == submission_id,
        FBRSubmission.tenant_id == tenant.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    retried_sub = FBRService.retry_submission(
        db=db,
        submission_id=submission_id,
        user_id=current_user.id,
        user_email=current_user.email
    )
    return retried_sub


@router.post("/test-connection", response_model=FBRTestConnectionResponse)
def test_fbr_connection(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    tenant_settings = db.query(OrganizationSettings).filter(
        OrganizationSettings.organization_id == tenant.id
    ).first()
    fbr_mode = (tenant_settings.fbr_mode if tenant_settings else "DEMO").upper()
    cred = db.query(FBRCredential).filter(
        FBRCredential.organization_id == tenant.id,
        FBRCredential.is_active.is_(True),
    ).first()

    if fbr_mode in ("SANDBOX", "PRODUCTION"):
        token = (cred.get_auth_token() or cred.get_api_key()) if cred else None
        token = token or (tenant_settings.fbr_api_token if tenant_settings else None) or app_settings.FBR_API_KEY
        probe_result = check_fbr_token(token or "")
    else:
        probe_result = {
            "success": False,
            "status": "NOT_APPLICABLE",
            "message": "DEMO mode does not verify credentials against FBR",
            "latency_ms": 0,
        }

    now = datetime.now(timezone.utc)
    if cred:
        cred.last_tested_at = now
        cred.environment = fbr_mode
        if probe_result["success"]:
            cred.last_success_at = now
            cred.status = "VERIFIED"
            cred.last_error = None
        else:
            cred.last_failed_at = now
            cred.status = (
                "AUTH_FAILED" if probe_result["status"] == "AUTH_FAILED"
                else "CONFIGURED_NOT_VERIFIED" if probe_result["status"] == "NOT_APPLICABLE"
                else "CONNECTION_UNAVAILABLE"
            )
            cred.last_error = probe_result["message"]
        db.commit()

    return FBRTestConnectionResponse(
        status=probe_result["status"],
        environment=fbr_mode,
        message=probe_result["message"],
        success=probe_result["success"],
        latency_ms=probe_result["latency_ms"],
        details={
            "official_reference_verified": probe_result["success"],
            "endpoint": "FBR /pdi/v1/provinces",
            "is_simulated": False,
        },
    )


@router.post("/certification/run")
def run_pral_certification_cycle(
    forced_adapter_mode: str = Query("SANDBOX", description="Adapter mode to certify: SANDBOX or PRODUCTION"),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Executes the official 5-cycle FBR/PRAL Pre-Production Certification suite."""
    from backend.app.services.fbr_certification_service import FBRCertificationService
    from backend.app.models.taxpayer import Taxpayer
    from backend.app.models.branch import Branch
    from backend.app.services.audit_service import AuditService

    taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant.id).first()
    taxpayer_ntn = taxpayer.ntn if taxpayer else "1234567-8"

    main_branch = db.query(Branch).filter(Branch.tenant_id == tenant.id, Branch.is_main == True).first()
    pos_id = main_branch.fbr_pos_id if main_branch and main_branch.fbr_pos_id else "10001"

    report = FBRCertificationService.run_full_certification_suite(
        tenant_id=tenant.id,
        taxpayer_ntn=taxpayer_ntn,
        pos_id=pos_id,
        forced_adapter_mode=forced_adapter_mode,
    )

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="FBR_CERTIFICATION_RUN",
        entity="PRAL_Certification",
        entity_id=report["dossier_id"],
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={
            "dossier_id": report["dossier_id"],
            "certified": report["certified"],
            "score": report["compliance_score"],
            "status": report["certification_status"]
        }
    )

    return report


@router.get("/certification/certificate-info")
def get_fbr_certificate_info(
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Audits the active client TLS certificate against PRAL digital signature requirements."""
    from backend.app.adapters.security.tls_security import parse_and_verify_certificate, CertificateValidationError
    from backend.app.core.config import settings

    cert_path = settings.FBR_CLIENT_CERT_PATH
    if not cert_path or not os.path.isfile(cert_path):
        return {
            "configured": False,
            "message": "No client certificate configured in FBR_CLIENT_CERT_PATH (using software sandbox profile)",
            "required_key_type": "RSA >= 2048-bit or ECC >= 256-bit",
            "format": "X.509 PEM",
        }

    try:
        info = parse_and_verify_certificate(cert_path)
        info["configured"] = True
        return info
    except CertificateValidationError as err:
        return {
            "configured": True,
            "is_valid": False,
            "validation_errors": [str(err)],
        }

