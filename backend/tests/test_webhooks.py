import time
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.security import (
    generate_webhook_secret,
    sign_webhook_payload,
    verify_webhook_signature,
    get_password_hash,
    create_access_token
)
from backend.app.models.tenant import Organization
from backend.app.models.user import User, UserRole
from backend.app.models.webhook import WebhookEndpoint, WebhookDelivery


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def webhook_test_env():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-wh-{uid}"

    org = Organization(id=tenant_id, name="Webhook Org", slug=f"wh-{uid}", plan="ENTERPRISE")
    user = User(
        id=f"user-wh-{uid}",
        tenant_id=tenant_id,
        email=f"wh-{uid}@example.com",
        hashed_password=get_password_hash("Password123!"),
        full_name="Webhook Admin",
        role=UserRole.ORG_ADMIN.value,
        is_active=True
    )
    db.add_all([org, user])
    db.commit()

    token = create_access_token(user.id, tenant_id, user.role)

    yield {
        "db": db,
        "tenant_id": tenant_id,
        "token": token,
    }
    db.close()


def test_hmac_sha256_signature_and_tampering():
    """Verify HMAC signature generation, successful verification, and tampering rejection."""
    secret = generate_webhook_secret()
    payload = b'{"event":"invoice.fbr_accepted","invoice_id":"inv-123"}'
    timestamp = int(time.time())

    # Compute valid signature
    sig_header = sign_webhook_payload(secret, payload, timestamp)
    assert sig_header.startswith(f"t={timestamp},v1=")

    # Verify signature
    assert verify_webhook_signature(secret, payload, sig_header, tolerance_seconds=300) is True

    # Tampered payload must fail
    tampered_payload = b'{"event":"invoice.fbr_accepted","invoice_id":"inv-999"}'
    assert verify_webhook_signature(secret, tampered_payload, sig_header, tolerance_seconds=300) is False

    # Stale timestamp (replay attack) must fail
    stale_timestamp = timestamp - 1000
    stale_sig = sign_webhook_payload(secret, payload, stale_timestamp)
    assert verify_webhook_signature(secret, payload, stale_sig, tolerance_seconds=300) is False


def test_webhook_endpoint_registration_and_testing(test_client, webhook_test_env):
    """Test registering webhook endpoint, test ping, and deleting endpoint."""
    headers = {"Authorization": f"Bearer {webhook_test_env['token']}"}

    # 1. Register Webhook Endpoint
    resp = test_client.post(
        "/api/v1/webhooks/endpoints",
        headers=headers,
        json={
            "url": "https://erp.customer.example/api/fbr-webhooks",
            "description": "Customer ERP Webhook Receiver",
            "events": ["invoice.created", "invoice.fbr_accepted", "invoice.fbr_rejected"]
        }
    )
    assert resp.status_code == 201
    ep_data = resp.json()
    assert ep_data["url"] == "https://erp.customer.example/api/fbr-webhooks"
    assert ep_data["secret"].startswith("whsec_")
    endpoint_id = ep_data["id"]

    # 2. List Webhook Endpoints
    resp = test_client.get("/api/v1/webhooks/endpoints", headers=headers)
    assert resp.status_code == 200
    endpoints = resp.json()
    assert len(endpoints) >= 1
    assert any(e["id"] == endpoint_id for e in endpoints)

    # 3. Test Ping Event
    resp = test_client.post(f"/api/v1/webhooks/endpoints/{endpoint_id}/test", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # 4. Delete Webhook Endpoint
    resp = test_client.delete(f"/api/v1/webhooks/endpoints/{endpoint_id}", headers=headers)
    assert resp.status_code == 204

    # Verify deletion
    resp = test_client.get("/api/v1/webhooks/endpoints", headers=headers)
    assert not any(e["id"] == endpoint_id for e in resp.json())
