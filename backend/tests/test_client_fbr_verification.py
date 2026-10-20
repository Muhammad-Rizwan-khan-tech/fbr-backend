"""Admin verification must reflect PRAL auth checks, not whether a token was stored."""
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, SessionLocal, engine
from backend.app.models.fbr_credential import FBRCredential
from backend.app.models.tenant import Organization, OrganizationSettings

client = TestClient(app)


def test_admin_client_verification_tracks_reference_api_status():
    Base.metadata.create_all(bind=engine)
    uid = uuid.uuid4().hex[:12]
    org_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        org = Organization(id=org_id, name="FBR Auth Test " + uid, slug="fbr-auth-" + uid)
        org_settings = OrganizationSettings(organization_id=org_id, fbr_mode="SANDBOX")
        cred = FBRCredential(organization_id=org_id, environment="SANDBOX", provider="SANDBOX")
        cred.set_credentials(auth_token="local-fake-test-token")
        db.add_all([org, org_settings, cred])
        db.commit()

        uri = f"/api/v1/admin/clients/{org_id}/fbr-connection/test"
        unauth = client.post(uri)
        assert unauth.status_code == 401
        headers = {"X-Admin-Key": settings.ADMIN_API_KEY}

        with patch("backend.app.api.routes.admin.check_fbr_token", return_value={
            "success": False, "status": "AUTH_FAILED", "message": "Unauthorized",
            "latency_ms": 19,
        }):
            denied = client.post(uri, headers=headers)
        assert denied.status_code == 200
        assert denied.json()["success"] is False
        assert denied.json()["fbr_status"] == "Authentication Failed"
        db.expire_all()
        assert db.query(FBRCredential).filter_by(organization_id=org_id).one().status == "AUTH_FAILED"

        with patch("backend.app.api.routes.admin.check_fbr_token", return_value={
            "success": True, "status": "VERIFIED", "message": "Reference authenticated",
            "latency_ms": 25,
        }) as official_probe:
            verified = client.post(uri, headers=headers)
            official_probe.assert_called_once_with("local-fake-test-token")
        assert verified.status_code == 200
        assert verified.json()["success"] is True
        assert verified.json()["fbr_status"] == "Verified"
        assert "local-fake-test-token" not in verified.text

        summary = client.get("/api/v1/admin/clients", headers=headers)
        assert summary.status_code == 200
        client_row = next(x for x in summary.json()["items"] if x["id"] == org_id)
        assert client_row["fbr_status"] == "Verified"
        assert client_row["fbr_environment"] == "SANDBOX"
    finally:
        db.rollback()
        db.query(FBRCredential).filter_by(organization_id=org_id).delete()
        db.query(OrganizationSettings).filter_by(organization_id=org_id).delete()
        db.query(Organization).filter_by(id=org_id).delete()
        db.commit()
        db.close()
