import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.config import settings
from backend.app.core.crypto import encrypt_secret, decrypt_secret, mask_secret, hash_activation_secret
from backend.app.models.tenant import Organization, OrgStatus
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.user import User, UserRole
from backend.app.models.license import License, LicenseStatus, ActivationKey, ActivationKeyStatus
from backend.app.models.device import DeviceInstallation, DeviceStatus
from backend.app.models.session import DeviceSession
from backend.app.models.fbr_credential import FBRCredential, FBRConnectionStatus
from backend.app.services.license_service import LicenseService

from backend.app.core.database import SessionLocal, Base, engine

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


def test_crypto_encryption_and_masking():
    """Verify AES-256-GCM encryption at rest and masking."""
    plaintext = "super_secret_fbr_token_12345"
    encrypted = encrypt_secret(plaintext)
    assert encrypted is not None
    assert encrypted != plaintext

    decrypted = decrypt_secret(encrypted)
    assert decrypted == plaintext

    masked = mask_secret(plaintext, visible_chars=4)
    assert masked.startswith("supe")
    assert masked.endswith("2345")
    assert "secret" not in masked


def test_server_to_server_admin_auth():
    """Verify X-Admin-Key protection for Super Admin platform endpoints."""
    # Unauthorized request (no header)
    resp = client.get("/api/v1/admin/stats")
    assert resp.status_code == 401

    # Unauthorized request (invalid key)
    resp = client.get("/api/v1/admin/stats", headers={"X-Admin-Key": "invalid-key"})
    assert resp.status_code == 401

    # Authorized request (valid X-Admin-Key)
    resp = client.get("/api/v1/admin/stats", headers={"X-Admin-Key": settings.ADMIN_API_KEY})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_organizations" in data
    assert "total_licenses" in data


def test_admin_create_organization_and_activation():
    """Verify organization creation, permanent license issuance, and desktop activation workflow."""
    admin_headers = {"X-Admin-Key": settings.ADMIN_API_KEY}

    uid = uuid.uuid4().hex[:6]
    payload = {
        "name": f"Testing Enterprises {uid} Pvt Ltd",
        "ntn": f"7{uid[:5]}-0",
        "strn": f"32778761{uid}",
        "province": "Sindh",
        "address": "Clifton Block 2, Karachi",
        "admin_email": f"admin_{uid}@testingenterprises.pk",
        "admin_name": "Tariq Mahmood",
        "max_devices": 2,
        "fbr_environment": "DEMO",
        "fbr_provider": "MOCK",
        "fbr_pos_id": "POS-TEST-01",
        "fbr_api_key": "fbr_key_secret_abc",
    }

    create_resp = client.post("/api/v1/admin/organizations", json=payload, headers=admin_headers)
    assert create_resp.status_code == 200
    create_data = create_resp.json()

    assert create_data["success"] is True
    assert "one_time_activation_secret" in create_data
    act_secret = create_data["one_time_activation_secret"]
    org_id = create_data["organization_id"]

    # 1. First-time desktop client activation
    device_fp_1 = "hardware-uuid-laptop-01-abcd"
    redeem_payload_1 = {
        "activation_key": act_secret,
        "device_fingerprint": device_fp_1,
        "device_name": "Karachi Terminal 1",
        "os_info": "Windows 11 Pro 64-bit",
        "app_version": "1.0.0",
    }

    redeem_resp = client.post("/api/v1/activation/redeem", json=redeem_payload_1)
    assert redeem_resp.status_code == 200
    redeem_data = redeem_resp.json()

    assert redeem_data["success"] is True
    assert "access_token" in redeem_data
    assert "refresh_token" in redeem_data
    token = redeem_data["access_token"]
    refresh_token = redeem_data["refresh_token"]
    assert redeem_data["license"]["license_type"] == "PERMANENT"
    assert redeem_data["license"]["status"] == "ACTIVE"

    # 2. Key Replay Prevention: Attempt to redeem the SAME activation secret again
    replay_resp = client.post("/api/v1/activation/redeem", json={
        "activation_key": act_secret,
        "device_fingerprint": "hardware-uuid-laptop-02-xyz",
        "device_name": "Lahore Terminal 2",
    })
    assert replay_resp.status_code == 400
    assert "already been redeemed" in replay_resp.text.lower()

    # 3. Access protected desktop endpoint using access token
    auth_headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/v1/me", headers=auth_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["organization"]["id"] == org_id

    # 4. Check real-time permanent license status
    lic_resp = client.get("/api/v1/license/status", headers=auth_headers)
    assert lic_resp.status_code == 200
    assert lic_resp.json()["is_valid"] is True
    assert lic_resp.json()["license_type"] == "PERMANENT"

    # 5. Token refresh with token rotation
    refresh_payload = {
        "refresh_token": refresh_token,
        "device_fingerprint": device_fp_1,
    }
    refresh_resp = client.post("/api/v1/auth/refresh", json=refresh_payload)
    assert refresh_resp.status_code == 200
    refreshed_data = refresh_resp.json()
    assert "access_token" in refreshed_data
    assert "refresh_token" in refreshed_data
    new_token = refreshed_data["access_token"]
    new_refresh = refreshed_data["refresh_token"]
    assert new_refresh != refresh_token  # Rotated!

    # 6. Device Fingerprint mismatch on refresh is rejected
    mismatch_resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": new_refresh,
        "device_fingerprint": "spoofed-fingerprint-999",
    })
    assert mismatch_resp.status_code in (401, 403)

    # 7. Re-issuing an activation key allows second device activation up to max_devices
    reissue_resp = client.post(
        f"/api/v1/admin/organizations/{org_id}/licenses/reissue",
        json={"reason": "Adding Branch terminal"},
        headers=admin_headers,
    )
    assert reissue_resp.status_code == 200
    new_act_secret = reissue_resp.json()["one_time_activation_secret"]

    device_fp_2 = "hardware-uuid-laptop-02-efgh"
    redeem_resp_2 = client.post("/api/v1/activation/redeem", json={
        "activation_key": new_act_secret,
        "device_fingerprint": device_fp_2,
        "device_name": "Terminal 2",
    })
    assert redeem_resp_2.status_code == 200
    device_2_id = redeem_resp_2.json()["device_id"]

    # 8. Device limit exceeded: Re-issuing for a 3rd device when max_devices=2 is blocked
    reissue_resp_3 = client.post(
        f"/api/v1/admin/organizations/{org_id}/licenses/reissue",
        json={"reason": "3rd device attempt"},
        headers=admin_headers,
    )
    assert reissue_resp_3.status_code == 200
    secret_3 = reissue_resp_3.json()["one_time_activation_secret"]

    redeem_resp_3 = client.post("/api/v1/activation/redeem", json={
        "activation_key": secret_3,
        "device_fingerprint": "hardware-uuid-laptop-03-blocked",
        "device_name": "Terminal 3",
    })
    assert redeem_resp_3.status_code == 403
    assert "limit reached" in redeem_resp_3.text.lower()

    # 9. Admin revokes Device 2
    revoke_dev_resp = client.put(
        f"/api/v1/admin/devices/{device_2_id}/revoke",
        json={"reason": "Terminal reported compromised"},
        headers=admin_headers,
    )
    assert revoke_dev_resp.status_code == 200
    assert revoke_dev_resp.json()["status"] == "REVOKED"

    # 10. Admin revokes License
    license_id = create_data["license_id"]
    revoke_lic_resp = client.put(
        f"/api/v1/admin/licenses/{license_id}/revoke",
        json={"reason": "Contract terminated"},
        headers=admin_headers,
    )
    assert revoke_lic_resp.status_code == 200

    # Verification: License status endpoint now reports invalid
    lic_status_after = client.get("/api/v1/license/status", headers={"Authorization": f"Bearer {new_token}"})
    assert lic_status_after.status_code == 200
    assert lic_status_after.json()["is_valid"] is False
    assert lic_status_after.json()["status"] == "REVOKED"


def test_fbr_credential_encryption_and_masked_api():
    """Verify admin configuration and encryption of FBR credentials."""
    admin_headers = {"X-Admin-Key": settings.ADMIN_API_KEY}

    uid = uuid.uuid4().hex[:6]
    # Create test org
    org_resp = client.post("/api/v1/admin/organizations", json={
        "name": f"Cred Test Org {uid}",
        "ntn": f"1{uid[:5]}-5",
        "province": "Punjab",
        "address": "Lahore Cantt",
        "admin_email": f"admin_{uid}@credtest.pk",
        "admin_name": "Cred Admin",
    }, headers=admin_headers)
    org_id = org_resp.json()["organization_id"]

    # Set FBR credentials
    set_cred_resp = client.post(
        f"/api/v1/admin/organizations/{org_id}/fbr-credentials",
        json={
            "environment": "SANDBOX",
            "provider": "SANDBOX",
            "fbr_pos_id": "POS-SND-99",
            "api_key": "raw_sensitive_sandbox_key_998877",
            "auth_token": "raw_sensitive_token_332211",
        },
        headers=admin_headers,
    )
    assert set_cred_resp.status_code == 200
    cred_data = set_cred_resp.json()["credentials"]

    assert cred_data["fbr_pos_id"] == "POS-SND-99"
    assert "raw_sensitive" not in cred_data["masked_api_key"]
    assert "****" in cred_data["masked_api_key"]
    assert "raw_sensitive" not in cred_data["masked_auth_token"]

    # Test FBR connection endpoint
    test_conn_resp = client.post(
        f"/api/v1/admin/organizations/{org_id}/fbr-test-connection",
        headers=admin_headers,
    )
    assert test_conn_resp.status_code == 200
    assert "status" in test_conn_resp.json()


def test_e2e_desktop_activation_and_invoicing_flow():
    """Complete E2E workflow:
    1. Admin creates customer organization via Super Admin API
    2. One-time activation key generated & revealed
    3. Desktop application redeems activation key with device hardware fingerprint
    4. Hardware is atomically bound, access and refresh tokens issued
    5. Client validates session via /me and checks permanent license status
    6. Client creates a tax invoice through fiscal engine with 18% GST
    7. Client lists invoices and verifies fiscal calculations
    """
    admin_headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    uid = uuid.uuid4().hex[:6]

    # 1. Super Admin creates Organization
    create_payload = {
        "name": f"Al-Rahim Hardware {uid} Pvt Ltd",
        "ntn": f"8{uid[:5]}-9",
        "strn": f"32778762{uid}",
        "province": "Punjab",
        "address": "Ferozepur Road, Lahore",
        "admin_email": f"finance_{uid}@alrahim.pk",
        "admin_name": "Rahim Khan",
        "max_devices": 3,
        "fbr_environment": "DEMO",
        "fbr_provider": "MOCK",
        "fbr_pos_id": f"POS-{uid.upper()}",
        "fbr_api_key": "al_rahim_fbr_secret_key",
    }
    create_resp = client.post("/api/v1/admin/organizations", json=create_payload, headers=admin_headers)
    assert create_resp.status_code == 200
    create_data = create_resp.json()
    act_key = create_data["one_time_activation_secret"]
    org_id = create_data["organization_id"]

    # 2. Desktop Client First-Time Activation
    device_fp = f"win11-hardware-uuid-{uid}"
    redeem_resp = client.post("/api/v1/activation/redeem", json={
        "activation_key": act_key,
        "device_fingerprint": device_fp,
        "device_name": "Main POS Terminal",
        "os_info": "Windows 11 Pro",
        "app_version": "1.0.0",
    })
    assert redeem_resp.status_code == 200
    redeem_data = redeem_resp.json()
    token = redeem_data["access_token"]
    assert redeem_data["organization"]["id"] == org_id
    assert redeem_data["license"]["license_type"] == "PERMANENT"
    assert redeem_data["license"]["status"] == "ACTIVE"

    # 3. Client Session & License Verification
    auth_headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/v1/me", headers=auth_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["organization"]["name"] == f"Al-Rahim Hardware {uid} Pvt Ltd"

    lic_resp = client.get("/api/v1/license/status", headers=auth_headers)
    assert lic_resp.status_code == 200
    assert lic_resp.json()["is_valid"] is True
    assert lic_resp.json()["license_type"] == "PERMANENT"

    fbr_status_resp = client.get("/api/v1/fbr/connection/status", headers=auth_headers)
    assert fbr_status_resp.status_code == 200
    assert fbr_status_resp.json()["is_configured"] is True

    # 4. Fetch Branch ID and create Customer for Invoice Creation
    branches_resp = client.get("/api/v1/branches", headers=auth_headers)
    assert branches_resp.status_code == 200
    branches = branches_resp.json()
    assert len(branches) > 0
    branch_id = branches[0]["id"]

    cust_resp = client.post("/api/v1/customers", json={
        "name": "Karachi Industrial Supply Corp",
        "ntn": "7654321-0",
        "strn": "1122334455667",
        "registration_type": "REGISTERED",
        "buyer_type": "REGISTERED_BUSINESS",
        "address": "S.I.T.E Area",
        "city": "Karachi",
        "province": "Sindh"
    }, headers=auth_headers)
    assert cust_resp.status_code == 200
    cust_id = cust_resp.json()["id"]

    # 5. Create Tax Invoice via Fiscal Engine
    inv_payload = {
        "branch_id": branch_id,
        "customer_id": cust_id,
        "payment_terms": "NET_15",
        "notes": "Payment due within 15 days",
        "items": [
            {
                "item_code": "FAST-M12-100",
                "description": "High-Tensile Steel Fasteners M12",
                "hs_code": "7318.15.00",
                "uom": "NUM",
                "quantity": 100.0,
                "unit_price": 50.0,
                "discount": 500.0,
                "tax_rate": 18.0,
                "sale_type": "STANDARD",
            }
        ]
    }
    inv_create_resp = client.post("/api/v1/invoices", json=inv_payload, headers=auth_headers)
    assert inv_create_resp.status_code == 201
    created_inv = inv_create_resp.json()
    invoice_id = created_inv["id"]

    # Check deterministic fiscal calculations:
    # 100 * 50 = 5000; 500 discount; taxable = 4500
    # 18% GST of 4500 = 810.00; total = 5310.00
    assert float(created_inv["subtotal"]) == 5000.0
    assert float(created_inv["total_discount"]) == 500.0
    assert float(created_inv["taxable_amount"]) == 4500.0
    assert float(created_inv["total_tax"]) == 810.0
    assert float(created_inv["grand_total"]) == 5310.0

    # 6. Verify invoice appears in Desktop invoice list
    list_resp = client.get("/api/v1/invoices", headers=auth_headers)
    assert list_resp.status_code == 200
    inv_ids = [inv["id"] for inv in list_resp.json()]
    assert invoice_id in inv_ids

