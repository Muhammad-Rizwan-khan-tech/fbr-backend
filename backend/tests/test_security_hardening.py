import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.security import validate_password_strength, get_password_hash
from backend.app.models.tenant import Organization
from backend.app.models.user import User, UserRole
from backend.app.models.invoice import Invoice, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.core.security import create_access_token


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def security_test_env():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    tenant_a_id = f"tenant-sec-a-{uid}"
    tenant_b_id = f"tenant-sec-b-{uid}"

    org_a = Organization(id=tenant_a_id, name="Security Org A", slug=f"sec-a-{uid}", plan="STANDARD")
    org_b = Organization(id=tenant_b_id, name="Security Org B", slug=f"sec-b-{uid}", plan="STANDARD")

    user_a = User(
        id=f"user-a-{uid}",
        tenant_id=tenant_a_id,
        email=f"user-a-{uid}@example.com",
        hashed_password=get_password_hash("Password123!"),
        full_name="User A",
        role=UserRole.ORG_ADMIN.value,
        is_active=True
    )
    user_b = User(
        id=f"user-b-{uid}",
        tenant_id=tenant_b_id,
        email=f"user-b-{uid}@example.com",
        hashed_password=get_password_hash("Password123!"),
        full_name="User B",
        role=UserRole.ORG_ADMIN.value,
        is_active=True
    )

    branch_a = Branch(id=f"br-a-{uid}", tenant_id=tenant_a_id, branch_name="Branch A", branch_code="BR-A", address="Address A", city="Karachi", province="Sindh", is_main=True, is_active=True)
    branch_b = Branch(id=f"br-b-{uid}", tenant_id=tenant_b_id, branch_name="Branch B", branch_code="BR-B", address="Address B", city="Karachi", province="Sindh", is_main=True, is_active=True)

    cust_a = Customer(
        id=f"cust-a-{uid}",
        tenant_id=tenant_a_id,
        name="Customer A",
        address="123 Street",
        city="Karachi",
        province="Sindh",
        registration_type="REGISTERED",
        buyer_type="B2B"
    )

    inv_a = Invoice(
        id=f"inv-a-{uid}",
        tenant_id=tenant_a_id,
        branch_id=branch_a.id,
        customer_id=cust_a.id,
        invoice_number=f"INV-SEC-A-{uid}",
        invoice_type="TAX_INVOICE",
        seller_branch_code="BR-A",
        seller_name="Seller A",
        seller_ntn="1234567-8",
        seller_province="Sindh",
        buyer_name="Buyer A",
        buyer_address="123 Street",
        buyer_province="Sindh",
        buyer_registration_type="REGISTERED",
        taxable_amount=1000,
        total_tax=180,
        grand_total=1180,
        status=InvoiceStatus.READY.value,
        fbr_status=FBRSubmissionStatus.NOT_SUBMITTED.value
    )

    db.add_all([org_a, org_b, user_a, user_b, branch_a, branch_b, cust_a, inv_a])
    db.commit()

    token_a = create_access_token(user_a.id, tenant_a_id, user_a.role)
    token_b = create_access_token(user_b.id, tenant_b_id, user_b.role)

    yield {
        "db": db,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "token_a": token_a,
        "token_b": token_b,
        "inv_a_id": inv_a.id,
    }
    db.close()


def test_security_headers_present(test_client):
    """Verify HTTP security headers are set on all responses."""
    resp = test_client.get("/health/live")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in resp.headers


def test_password_strength_validation():
    """Verify password strength validation rules."""
    ok, err = validate_password_strength("short")
    assert not ok
    assert "at least 8" in err

    ok, err = validate_password_strength("alllettersonly")
    assert not ok
    assert "letters and numbers" in err

    ok, err = validate_password_strength("SecurePass123")
    assert ok
    assert err is None


def test_idor_cross_tenant_access_denied(test_client, security_test_env):
    """Verify that User B from Tenant B cannot access Invoice A belonging to Tenant A (IDOR defense)."""
    headers_b = {"Authorization": f"Bearer {security_test_env['token_b']}"}
    inv_a_id = security_test_env["inv_a_id"]

    # User B tries to view Invoice A
    resp = test_client.get(f"/api/v1/invoices/{inv_a_id}", headers=headers_b)
    assert resp.status_code == 404, "User B should receive 404 when querying Tenant A's invoice"

    # User B tries to validate Invoice A
    resp = test_client.post(f"/api/v1/invoices/{inv_a_id}/validate", headers=headers_b)
    assert resp.status_code == 404

    # User B tries to queue submit Invoice A
    resp = test_client.post(f"/api/v1/invoices/{inv_a_id}/queue-submit", headers=headers_b)
    assert resp.status_code == 404


def test_rate_limiting_enforcement(test_client):
    """Verify that excessive requests trip the rate limiter."""
    from backend.app.core.middleware import check_rate_limit
    from backend.app.core.errors import RateLimitError
    from fastapi import Request

    dummy_req = Request(scope={"type": "http", "client": ("127.0.0.1", 12345), "headers": []})
    
    # 5 allowed requests within 60s
    for _ in range(5):
        check_rate_limit(dummy_req, scope="test_rl", limit=5, window_seconds=60, identity_override="test_user_rl")

    # 6th request must trip rate limit
    with pytest.raises(RateLimitError) as exc_info:
        check_rate_limit(dummy_req, scope="test_rl", limit=5, window_seconds=60, identity_override="test_user_rl")
    assert exc_info.value.status_code == 429
