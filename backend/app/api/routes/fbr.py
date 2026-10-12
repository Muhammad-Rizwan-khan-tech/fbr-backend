import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.user import User
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.fbr import FBRSubmission, FBRSubmissionAttempt
from backend.app.schemas.fbr import (
    FBRSubmissionResponse, FBRStatusResponse, FBRTestConnectionResponse
)
from backend.app.services.fbr_service import FBRService
from backend.app.adapters.factory import FBRAdapterFactory

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

    last_sub = db.query(FBRSubmission).filter(
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status == "VALID"
    ).order_by(FBRSubmission.submitted_at.desc()).first()

    pending_count = db.query(FBRSubmission).filter(
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status == "PENDING"
    ).count()

    failed_count = db.query(FBRSubmission).filter(
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status.in_(["FAILED", "INVALID"])
    ).count()

    valid_count = db.query(FBRSubmission).filter(
        FBRSubmission.tenant_id == tenant.id,
        FBRSubmission.status == "VALID"
    ).count()

    return FBRStatusResponse(
        is_connected=True,
        environment=fbr_mode,
        adapter="MockFBRAdapter" if fbr_mode in ("DEMO", "MOCK") else "LicensedIntegratorAdapter",
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
    query = db.query(FBRSubmission).filter(FBRSubmission.tenant_id == tenant.id)
    if status:
        query = query.filter(FBRSubmission.status == status.upper())
    return query.order_by(FBRSubmission.submitted_at.desc()).limit(limit).all()


@router.get("/submissions/{submission_id}", response_model=FBRSubmissionResponse)
def get_submission_detail(
    submission_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    sub = db.query(FBRSubmission).filter(
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
    sub = db.query(FBRSubmission).filter(
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
    settings = db.query(OrganizationSettings).filter(
        OrganizationSettings.organization_id == tenant.id
    ).first()
    fbr_mode = settings.fbr_mode if settings else "DEMO"
    adapter = FBRAdapterFactory.get_adapter(fbr_mode, tenant_settings=settings)
    probe_result = adapter.test_connection()

    return FBRTestConnectionResponse(
        status=probe_result.get("status", "ONLINE"),
        environment=fbr_mode,
        message=probe_result.get("message", f"Connected to FBR [{fbr_mode}] gateway"),
        success=probe_result.get("success", True),
        latency_ms=probe_result.get("latency_ms", 0),
        details=probe_result
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

