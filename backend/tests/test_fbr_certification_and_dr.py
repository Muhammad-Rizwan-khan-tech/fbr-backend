"""Tests for FBR/PRAL Pre-Production Certification, mTLS, Developer Portal, and DR Drills."""

import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.core.security import create_access_token
from backend.app.adapters.security.tls_security import (
    generate_self_signed_certification_cert,
    parse_and_verify_certificate,
    CertificateValidationError,
)
from backend.app.services.fbr_certification_service import FBRCertificationService
from scripts.run_dr_drill import run_disaster_recovery_drill

client = TestClient(app)


def get_test_auth_headers():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "admin@abcdistribution.com").first()
        org = db.query(Organization).filter(Organization.id == user.tenant_id).first()
        token = create_access_token(subject=user.id, tenant_id=org.id, role=user.role)
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_mtls_client_certificate_generation_and_audit():
    """Verify X.509 client certificate parsing, key size, and compliance checks."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cert_path, key_path = generate_self_signed_certification_cert(
            output_dir=tmp_dir,
            org_name="PRAL Test Taxpayer Pvt Ltd",
            ntn="9988776-5",
            common_name="fbr-pos-test.pral.pk",
            validity_days=180,
        )
        assert cert_path.is_file()
        assert key_path.is_file()

        info = parse_and_verify_certificate(cert_path)
        assert info["is_valid"] is True
        assert info["key_algorithm"] == "RSA"
        assert info["key_size_bits"] == 2048
        assert info["is_key_compliant"] is True
        assert info["is_expired"] is False
        assert "9988776-5" in str(info["subject"])


def test_fbr_certification_service_five_cycles():
    """Verify that the 5 standardized certification transmission cycles execute to 100% score."""
    report = FBRCertificationService.run_full_certification_suite(
        tenant_id="test-cert-tenant",
        taxpayer_ntn="1234567-8",
        pos_id="10001",
        forced_adapter_mode="SANDBOX",
    )
    assert report["certified"] is True
    assert report["compliance_score"] == 100.0
    assert report["total_cycles"] == 5
    assert report["passed_cycles"] == 5
    assert report["certification_status"] == "CERTIFIED_FOR_PRODUCTION"
    assert "PRAL-CERT-" in report["dossier_id"]
    assert len(report["cryptographic_seal"]) == 64


def test_fbr_certification_api_endpoints():
    """Verify POST /api/v1/fbr/certification/run and certificate-info endpoints."""
    headers = get_test_auth_headers()

    # 1. Run Certification Cycle
    res_run = client.post("/api/v1/fbr/certification/run?forced_adapter_mode=SANDBOX", headers=headers)
    assert res_run.status_code == 200
    data = res_run.json()
    assert data["certified"] is True
    assert data["compliance_score"] == 100.0
    assert len(data["cycles"]) == 5

    # 2. Inspect Certificate Info
    res_cert = client.get("/api/v1/fbr/certification/certificate-info", headers=headers)
    assert res_cert.status_code == 200
    cert_data = res_cert.json()
    assert "format" in cert_data or "is_valid" in cert_data


def test_developer_documentation_portal_routes():
    """Verify GET /developer/portal and GET /docs/developer-guide serve HTML."""
    res_portal = client.get("/developer/portal")
    assert res_portal.status_code == 200
    assert "text/html" in res_portal.headers["content-type"]
    assert "FBR Invoice Cloud" in res_portal.text
    assert "SAP" in res_portal.text
    assert "Oracle" in res_portal.text
    assert "Odoo" in res_portal.text
    assert "HMAC-SHA256" in res_portal.text

    res_guide = client.get("/docs/developer-guide")
    assert res_guide.status_code == 200


def test_disaster_recovery_drill_verification_function():
    """Verify that run_disaster_recovery_drill verifies schema, row counts, and fiscal integrity."""
    src_db = Path("fbr_invoice_cloud.db").resolve()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        scratch_db = Path(tmp_dir) / "scratch_test.db"
        report = run_disaster_recovery_drill(src_db, scratch_db)
        assert report["overall_success"] is True
        assert report["status"] == "DRILL_PASSED"
        assert report["verifications"]["schema_integrity"]["passed"] is True
        assert report["verifications"]["record_reconciliation"]["passed"] is True
        assert report["verifications"]["foreign_key_integrity"]["passed"] is True
        assert report["verifications"]["tenant_isolation_boundary"]["passed"] is True
        assert report["verifications"]["fiscal_balance_integrity"]["passed"] is True

        try:
            if scratch_db.exists():
                scratch_db.unlink(missing_ok=True)
        except Exception:
            pass
