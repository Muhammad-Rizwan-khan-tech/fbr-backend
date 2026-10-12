import uuid
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.user import User, UserRole


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def developer_test_env():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-dev-{uid}"

    org = Organization(id=tenant_id, name="Developer Org", slug=f"dev-org-{uid}", plan="ENTERPRISE")
    settings = OrganizationSettings(organization_id=tenant_id, fbr_mode="DEMO")
    taxpayer = Taxpayer(
        tenant_id=tenant_id,
        legal_name="Developer Corp Ltd",
        ntn="8888777-6",
        strn="8888777654321",
        address="I.I. Chundrigar Road",
        city="Karachi",
        province="Sindh"
    )
    branch = Branch(
        tenant_id=tenant_id,
        branch_name="Main Branch",
        branch_code="BR-MAIN",
        is_main=True,
        is_active=True,
        address="I.I. Chundrigar Road",
        city="Karachi",
        province="Sindh"
    )
    admin_user = User(
        id=f"user-dev-{uid}",
        tenant_id=tenant_id,
        email=f"admin-{uid}@developer.example",
        hashed_password=get_password_hash("Password123!"),
        full_name="Developer Admin",
        role=UserRole.ORG_ADMIN.value,
        is_active=True
    )

    db.add_all([org, settings, taxpayer, branch, admin_user])
    db.commit()

    token = create_access_token(admin_user.id, tenant_id, admin_user.role)

    yield {
        "db": db,
        "tenant_id": tenant_id,
        "token": token,
        "branch_code": branch.branch_code,
    }
    db.close()


def test_api_key_lifecycle(test_client, developer_test_env):
    """Test API key creation, listing (masked), rotation, and revocation."""
    headers = {"Authorization": f"Bearer {developer_test_env['token']}"}

    # 1. Create API Key
    resp = test_client.post(
        "/api/v1/developer/keys",
        headers=headers,
        json={
            "name": "SAP Integration Key",
            "environment": "TEST",
            "scopes": ["invoices:read", "invoices:write"],
            "rate_limit_per_minute": 100
        }
    )
    assert resp.status_code == 201
    key_data = resp.json()
    raw_key = key_data["raw_api_key"]
    key_id = key_data["id"]
    assert raw_key.startswith("fbr_test_")
    assert key_data["key_prefix"] == raw_key[:16]
    assert key_data["is_active"] is True

    # 2. List API Keys (confirm plaintext is NOT leaked)
    resp = test_client.get("/api/v1/developer/keys", headers=headers)
    assert resp.status_code == 200
    keys_list = resp.json()
    assert len(keys_list) >= 1
    found = next((k for k in keys_list if k["id"] == key_id), None)
    assert found is not None
    assert "raw_api_key" not in found
    assert found["key_prefix"] == raw_key[:16]

    # 3. Rotate API Key
    resp = test_client.post(f"/api/v1/developer/keys/{key_id}/rotate", headers=headers)
    assert resp.status_code == 200
    rotated_data = resp.json()
    new_raw_key = rotated_data["raw_api_key"]
    new_key_id = rotated_data["id"]
    assert new_raw_key != raw_key
    assert new_raw_key.startswith("fbr_test_")

    # 4. Revoke New Key
    resp = test_client.delete(f"/api/v1/developer/keys/{new_key_id}", headers=headers)
    assert resp.status_code == 204

    # Verify that rotated & revoked key is inactive
    resp = test_client.get("/api/v1/developer/keys", headers=headers)
    revoked_key = next((k for k in resp.json() if k["id"] == new_key_id), None)
    assert revoked_key["is_active"] is False


def test_external_invoice_ingestion_and_idempotency(test_client, developer_test_env):
    """Test external ERP invoice ingestion via X-API-Key and idempotency replay."""
    # Create API key
    admin_headers = {"Authorization": f"Bearer {developer_test_env['token']}"}
    resp = test_client.post(
        "/api/v1/developer/keys",
        headers=admin_headers,
        json={
            "name": "ERP Ingest Key",
            "environment": "TEST",
            "scopes": ["invoices:read", "invoices:write"],
            "rate_limit_per_minute": 100
        }
    )
    raw_api_key = resp.json()["raw_api_key"]

    api_headers = {
        "X-API-Key": raw_api_key,
        "Idempotency-Key": "SAP-INV-00129",
    }

    # Ingest invoice payload
    payload = {
        "branch_code": developer_test_env["branch_code"],
        "external_reference_id": "SAP-INV-00129",
        "buyer": {
            "name": "Acme Industries Pakistan",
            "ntn": "7766554-3",
            "strn": "7766554321098",
            "buyer_type": "REGISTERED_BUSINESS",
            "address": "Korangi Industrial Area",
            "city": "Karachi",
            "province": "Sindh"
        },
        "items": [
            {
                "item_code": "RAW-STL-01",
                "item_name": "Structural Steel Beams",
                "hs_code": "7216.31.00",
                "uom": "KGS",
                "quantity": 100.0,
                "unit_price": 250.0,
                "discount": 1000.0,
                "tax_rate": 18.0,
                "sale_type": "GOODS"
            }
        ],
        "payment_mode": "BANK_TRANSFER",
        "auto_submit_fbr": True
    }

    # First Ingestion
    resp = test_client.post("/api/v1/external/invoices", headers=api_headers, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["invoice_id"] is not None
    assert data["invoice_number"] is not None
    # 100 * 250 = 25000; - 1000 discount = 24000 taxable; * 18% = 4320 tax; total = 28320
    assert float(data["taxable_amount"]) == 24000.0
    assert float(data["total_tax"]) == 4320.0
    assert float(data["grand_total"]) == 28320.0
    assert data["fbr_status"] in ("PENDING", "QUEUED")
    invoice_id = data["invoice_id"]

    # Second Ingestion with identical external_reference_id (IDEMPOTENT REPLAY)
    resp2 = test_client.post("/api/v1/external/invoices", headers=api_headers, json=payload)
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["invoice_id"] == invoice_id
    assert "idempotent" in data2["message"].lower()

    # Query Status
    resp_status = test_client.get(f"/api/v1/external/invoices/{invoice_id}/status", headers={"X-API-Key": raw_api_key})
    assert resp_status.status_code == 200
    st_data = resp_status.json()
    assert st_data["invoice_id"] == invoice_id
    assert st_data["external_reference_id"] == "SAP-INV-00129"


def test_api_key_scope_protection(test_client, developer_test_env):
    """Test that an API key with only 'invoices:read' cannot write invoices."""
    admin_headers = {"Authorization": f"Bearer {developer_test_env['token']}"}
    resp = test_client.post(
        "/api/v1/developer/keys",
        headers=admin_headers,
        json={
            "name": "Read-Only Key",
            "environment": "TEST",
            "scopes": ["invoices:read"],
            "rate_limit_per_minute": 60
        }
    )
    raw_api_key = resp.json()["raw_api_key"]

    # Attempt to write invoice with read-only key
    resp = test_client.post(
        "/api/v1/external/invoices",
        headers={"X-API-Key": raw_api_key},
        json={
            "buyer": {"name": "Test"},
            "items": [{"item_name": "Test", "hs_code": "1234", "quantity": 1, "unit_price": 100}]
        }
    )
    assert resp.status_code == 403
    assert "invoices:write" in resp.json()["detail"]
