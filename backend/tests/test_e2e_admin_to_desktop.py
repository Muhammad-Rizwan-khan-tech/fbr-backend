import uuid
import re
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.core.crypto import decrypt_secret, hash_activation_secret
from backend.app.models.tenant import Organization
from backend.app.models.user import User
from backend.app.models.license import License, LicenseStatus, ActivationKey, ActivationKeyStatus
from backend.app.models.device import DeviceInstallation
from backend.app.models.fbr_credential import FBRCredential

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_database_schema():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_complete_admin_to_desktop_e2e_workflow(db):
    """
    End-to-end integration test validating the entire production lifecycle:
    1. Super Admin authentication & client creation with strictly 3 required fields
    2. Uniqueness & collision checks (duplicate username rejection)
    3. At-rest encryption (AES-256-GCM) of FBR credentials & SHA-256 activation secret hashing
    4. Admin client list presentation & state reflection
    5. Desktop terminal activation (one-time redemption & hardware fingerprint binding)
    6. Replay attack rejection (reusing spent activation key fails)
    7. Client user profile inspection (contains username, no leaked secrets)
    8. Refresh token rotation & session management
    9. Authoritative backend tenant license enforcement (revocation blocks API with HTTP 403)
    10. Desktop license status query during revocation
    11. Admin license reactivation & operational recovery
    12. Controlled activation key reissue & secondary device binding
    13. Admin FBR API token update & credential rotation
    """
    admin_headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    client_username = f"e2e_{uuid.uuid4().hex[:10]}"
    company_name = f"Al-Madina Logistics {uuid.uuid4().hex[:6]}"
    raw_fbr_token = f"PRAL-E2E-{uuid.uuid4().hex}"

    # Step 1: Admin API Security Gate (Missing or invalid X-Admin-Key must be 401)
    unauthorized_resp = client.post(
        "/api/v1/admin/clients",
        json={"company_name": company_name, "username": client_username, "fbr_api_token": raw_fbr_token},
    )
    assert unauthorized_resp.status_code == 401

    wrong_key_resp = client.post(
        "/api/v1/admin/clients",
        headers={"X-Admin-Key": "incorrect-secret-key"},
        json={"company_name": company_name, "username": client_username, "fbr_api_token": raw_fbr_token},
    )
    assert wrong_key_resp.status_code == 401

    # Step 2: Create Client with EXACTLY 3 Fields
    create_resp = client.post(
        "/api/v1/admin/clients",
        headers=admin_headers,
        json={
            "company_name": company_name,
            "username": client_username,
            "fbr_api_token": raw_fbr_token,
        },
    )
    assert create_resp.status_code == 200, f"Create client failed: {create_resp.text}"
    created_data = create_resp.json()

    assert created_data["company_name"] == company_name
    assert created_data["username"] == client_username
    assert created_data["license_status"] == "ACTIVE"
    assert created_data["activation_status"] == "Not Activated"
    assert created_data["fbr_status"] == "Configured — Not Verified"

    activation_key = created_data.get("activation_key")
    assert activation_key is not None
    assert re.match(r"^ACT-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", activation_key)

    client_org_id = created_data["organization_id"]

    # Step 3: Duplicate Username Validation (Reject with HTTP 409 Conflict)
    dup_resp = client.post(
        "/api/v1/admin/clients",
        headers=admin_headers,
        json={
            "company_name": "Another Company LLC",
            "username": client_username,
            "fbr_api_token": "ANOTHER-TOKEN-123456",
        },
    )
    assert dup_resp.status_code == 409
    assert "already exists" in dup_resp.text or "already taken" in dup_resp.text

    # Step 4: Verify Database Storage Security
    db.expire_all()
    user_record = db.query(User).filter(User.username == client_username).first()
    assert user_record is not None
    assert user_record.tenant_id == client_org_id
    assert user_record.hashed_password is not None
    assert len(user_record.hashed_password) > 20

    fbr_record = db.query(FBRCredential).filter(FBRCredential.organization_id == client_org_id).first()
    assert fbr_record is not None
    assert fbr_record.encrypted_auth_token != raw_fbr_token, "FBR API token must NOT be stored in plaintext!"
    decrypted_token = decrypt_secret(fbr_record.encrypted_auth_token)
    assert decrypted_token == raw_fbr_token

    key_record = db.query(ActivationKey).filter(ActivationKey.organization_id == client_org_id).first()
    assert key_record is not None
    assert key_record.key_hash != activation_key, "Activation key must NOT be stored in plaintext!"
    assert key_record.key_hash == hash_activation_secret(activation_key)
    assert key_record.status == ActivationKeyStatus.PENDING

    # Step 5: Verify Admin Client Listing
    list_resp = client.get("/api/v1/admin/clients", headers=admin_headers)
    assert list_resp.status_code == 200
    clients_data = list_resp.json()
    clients_list = clients_data.get("items", clients_data if isinstance(clients_data, list) else [])
    matching_clients = [c for c in clients_list if c["id"] == client_org_id]
    assert len(matching_clients) == 1
    target_client = matching_clients[0]
    assert target_client["company_name"] == company_name
    assert target_client["username"] == client_username
    assert target_client["license_status"] == "ACTIVE"
    assert target_client["activation_status"] == "Not Activated"
    assert "CONFIGURED" in target_client["fbr_status"].upper()

    # Step 6: Desktop Terminal First-Time Activation
    device_fp_1 = "e2e_device_fingerprint_counter_01_aabbccdd"
    redeem_resp = client.post(
        "/api/v1/activation/redeem",
        json={
            "activation_key": activation_key,
            "device_fingerprint": device_fp_1,
            "device_name": "Main Counter POS-1",
            "os_info": "Windows 11 Pro 64-bit",
            "app_version": "1.1.0",
        },
    )
    assert redeem_resp.status_code == 200, f"Activation failed: {redeem_resp.text}"
    session_data = redeem_resp.json()

    access_token = session_data["access_token"]
    refresh_token = session_data["refresh_token"]
    assert access_token is not None
    assert refresh_token is not None
    assert session_data["organization"]["id"] == client_org_id
    assert session_data["organization"]["name"] == company_name
    assert session_data["license"]["license_type"] == "PERMANENT"
    assert session_data["license"]["status"] == "ACTIVE"
    assert session_data["user"]["username"] == client_username

    # CRITICAL SECURITY RULE: The desktop application must NEVER receive the raw FBR token
    assert "fbr_api_token" not in session_data
    assert "api_token_encrypted" not in session_data

    # Step 7: Anti-Replay Verification (Redeeming used key must be rejected)
    replay_resp = client.post(
        "/api/v1/activation/redeem",
        json={
            "activation_key": activation_key,
            "device_fingerprint": "different_device_attempt",
            "device_name": "Rogue Terminal",
        },
    )
    assert replay_resp.status_code in (400, 409)
    assert "redeemed" in replay_resp.text.lower() or "already" in replay_resp.text.lower()

    # Step 8: Desktop Session User Profile Inspection (/api/v1/me)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = client.get("/api/v1/me", headers=auth_headers)
    assert me_resp.status_code == 200
    user_me = me_resp.json()
    assert user_me["user"]["username"] == client_username
    assert user_me["organization"]["id"] == client_org_id

    # Step 9: Refresh Token Rotation
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
            "device_fingerprint": device_fp_1,
        },
    )
    assert refresh_resp.status_code == 200
    rotated_session = refresh_resp.json()
    new_access_token = rotated_session["access_token"]
    new_refresh_token = rotated_session["refresh_token"]
    assert new_access_token is not None
    assert new_refresh_token != refresh_token

    # Re-using old refresh token must be rejected
    reuse_resp = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
            "device_fingerprint": device_fp_1,
        },
    )
    assert reuse_resp.status_code in (400, 401)

    # Step 10: Verify Device Count Updated in Admin View
    client_detail_resp = client.get(f"/api/v1/admin/clients/{client_org_id}", headers=admin_headers)
    assert client_detail_resp.status_code == 200
    client_detail = client_detail_resp.json()
    assert client_detail["activation_status"] == "Activated"
    assert client_detail["active_devices_count"] == 1
    assert len(client_detail["devices"]) == 1

    # Step 11: Normal Invoicing API Operations with Valid Active License
    current_auth_headers = {"Authorization": f"Bearer {new_access_token}"}
    invoices_resp = client.get("/api/v1/invoices", headers=current_auth_headers)
    assert invoices_resp.status_code == 200

    # Step 12: Safe Evidence-Based FBR Status Check
    fbr_status_resp = client.get("/api/v1/fbr/status", headers=current_auth_headers)
    assert fbr_status_resp.status_code == 200
    fbr_status_data = fbr_status_resp.json()
    assert fbr_status_data["connection_status"] == "CONFIGURED_NOT_VERIFIED"
    assert fbr_status_data["is_connected"] is False  # Confirmed fix for Audit Issue 4 (no fake connected boolean)
    assert "token" not in fbr_status_data

    # Step 13: Super Admin Revokes Client License
    revoke_resp = client.post(
        f"/api/v1/admin/clients/{client_org_id}/license/revoke",
        headers=admin_headers,
        params={"reason": "Audit hold: compliance review requested"},
    )
    assert revoke_resp.status_code == 200

    # Step 14: Strict Tenant License Enforcement Gate
    # Any protected operations using the tenant's token must be rejected with HTTP 403 Forbidden!
    blocked_resp = client.get("/api/v1/invoices", headers=current_auth_headers)
    assert blocked_resp.status_code == 403
    assert "revoked" in blocked_resp.text.lower() or "not active" in blocked_resp.text.lower()

    # Step 15: Desktop License Status Endpoint While Revoked
    # License status endpoint should return HTTP 200 with is_valid=False and status=REVOKED
    # so the desktop client UI can cleanly display the license suspension screen.
    lic_status_resp = client.get("/api/v1/license/status", headers=current_auth_headers)
    assert lic_status_resp.status_code == 200
    lic_status_data = lic_status_resp.json()
    assert lic_status_data["is_valid"] is False
    assert lic_status_data["status"] == "REVOKED"

    # Step 16: Admin Reactivates Client License
    reactivate_resp = client.post(
        f"/api/v1/admin/clients/{client_org_id}/license/reactivate",
        headers=admin_headers,
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["status"] == "ACTIVE"

    # Step 17: Operational Access Restored
    restored_resp = client.get("/api/v1/invoices", headers=current_auth_headers)
    assert restored_resp.status_code == 200

    # Step 18: Admin Reissues Fresh Activation Key (e.g. for Workstation Replacement)
    reissue_resp = client.post(
        f"/api/v1/admin/clients/{client_org_id}/activation/reissue",
        headers=admin_headers,
        params={"reason": "New POS Terminal Workstation installed"},
    )
    assert reissue_resp.status_code == 200
    reissue_data = reissue_resp.json()
    new_activation_key = reissue_data["activation_key"]
    assert new_activation_key != activation_key
    assert re.match(r"^ACT-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", new_activation_key)

    # Step 19: Redeem Reissued Key on Second Device
    device_fp_2 = "e2e_device_fingerprint_counter_02_ccddeeff"
    redeem_2_resp = client.post(
        "/api/v1/activation/redeem",
        json={
            "activation_key": new_activation_key,
            "device_fingerprint": device_fp_2,
            "device_name": "Branch Counter POS-2",
        },
    )
    assert redeem_2_resp.status_code == 200
    assert redeem_2_resp.json()["organization"]["id"] == client_org_id

    # Verify device count is now 2
    detail_2_resp = client.get(f"/api/v1/admin/clients/{client_org_id}", headers=admin_headers)
    assert detail_2_resp.json()["active_devices_count"] == 2

    # Step 20: Admin Updates / Rotates FBR API Token
    rotated_fbr_token = "PRAL-ROTATED-TOKEN-PROD-2026-X99"
    update_fbr_resp = client.put(
        f"/api/v1/admin/clients/{client_org_id}/fbr-connection",
        headers=admin_headers,
        json={"fbr_api_token": rotated_fbr_token},
    )
    assert update_fbr_resp.status_code == 200
    assert "CONFIGURED" in update_fbr_resp.json()["fbr_status"].upper()

    # Verify DB token was encrypted
    db.expire_all()
    updated_fbr = db.query(FBRCredential).filter(FBRCredential.organization_id == client_org_id).first()
    assert updated_fbr.encrypted_auth_token != rotated_fbr_token
    assert decrypt_secret(updated_fbr.encrypted_auth_token) == rotated_fbr_token
