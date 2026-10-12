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
from backend.app.models.invoice import Invoice, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.submission_job import InvoiceSubmissionJob
from backend.app.models.webhook import WebhookEndpoint, WebhookDelivery
from backend.app.workers.tasks import submit_invoice_to_fbr_task


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def e2e_env():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-e2e-{uid}"
    intruder_id = f"tenant-intruder-{uid}"

    # Main Tenant
    org = Organization(id=tenant_id, name="E2E Corporation", slug=f"e2e-{uid}", plan="ENTERPRISE")
    settings = OrganizationSettings(organization_id=tenant_id, fbr_mode="DEMO")
    taxpayer = Taxpayer(
        tenant_id=tenant_id,
        legal_name="E2E Corporation Ltd",
        ntn="9999888-1",
        strn="9999888123456",
        address="Blue Area",
        city="Islamabad",
        province="Federal"
    )
    branch = Branch(
        tenant_id=tenant_id,
        branch_name="Islamabad HQ",
        branch_code="HQ-ISB",
        is_main=True,
        is_active=True,
        address="Blue Area",
        city="Islamabad",
        province="Federal"
    )
    user = User(
        id=f"user-e2e-{uid}",
        tenant_id=tenant_id,
        email=f"e2e-{uid}@example.com",
        hashed_password=get_password_hash("Password123!"),
        full_name="E2E Operator",
        role=UserRole.ORG_ADMIN.value,
        is_active=True
    )

    # Intruder Tenant (to test tenant isolation)
    intruder_org = Organization(id=intruder_id, name="Intruder Corp", slug=f"intruder-{uid}", plan="STANDARD")
    intruder_user = User(
        id=f"user-intruder-{uid}",
        tenant_id=intruder_id,
        email=f"intruder-{uid}@example.com",
        hashed_password=get_password_hash("Password123!"),
        full_name="Intruder User",
        role=UserRole.ORG_ADMIN.value,
        is_active=True
    )

    db.add_all([org, settings, taxpayer, branch, user, intruder_org, intruder_user])
    db.commit()

    token = create_access_token(user.id, tenant_id, user.role)
    intruder_token = create_access_token(intruder_user.id, intruder_id, intruder_user.role)

    yield {
        "db": db,
        "tenant_id": tenant_id,
        "intruder_id": intruder_id,
        "token": token,
        "intruder_token": intruder_token,
        "branch_code": branch.branch_code,
    }
    db.close()


def test_end_to_end_invoice_fbr_webhook_and_pdf_flow(test_client, e2e_env):
    """Full-system end-to-end integration test:
    1. Register Developer API Key & Webhook Endpoint
    2. Ingest External ERP Invoice via API
    3. Verify Tax Calculations
    4. Worker executes FBR submission (Mock Adapter)
    5. FBR Acceptance and QR Code Generation
    6. PDF Generation & Signed URL Download
    7. Credit Note Issuance & Balance Ceiling Protection
    8. Strict Cross-Tenant Isolation Enforcement
    """
    admin_headers = {"Authorization": f"Bearer {e2e_env['token']}"}

    # Step 1: Create Developer API Key
    key_resp = test_client.post(
        "/api/v1/developer/keys",
        headers=admin_headers,
        json={"name": "E2E Key", "environment": "TEST", "scopes": ["invoices:read", "invoices:write"]}
    )
    assert key_resp.status_code == 201
    api_key = key_resp.json()["raw_api_key"]

    # Step 2: Register Webhook Endpoint (using localhost test target)
    wh_resp = test_client.post(
        "/api/v1/webhooks/endpoints",
        headers=admin_headers,
        json={
            "url": "http://localhost:8000/api/v1/health/live",
            "description": "E2E Webhook Receiver",
            "events": ["*"]
        }
    )
    assert wh_resp.status_code == 201
    endpoint_id = wh_resp.json()["id"]

    # Step 3: Ingest External Invoice via Developer API
    erp_headers = {"X-API-Key": api_key}
    invoice_payload = {
        "branch_code": e2e_env["branch_code"],
        "external_reference_id": f"ERP-REF-{uuid.uuid4().hex[:6]}",
        "buyer": {
            "name": "Standard Chartered Pakistan",
            "ntn": "1122334-5",
            "buyer_type": "REGISTERED_BUSINESS",
            "address": "Mall Road",
            "city": "Lahore",
            "province": "Punjab"
        },
        "items": [
            {
                "item_name": "Software Enterprise License",
                "hs_code": "8523.49.20",
                "uom": "NUM",
                "quantity": 2.0,
                "unit_price": 50000.0,
                "discount": 5000.0,
                "tax_rate": 18.0,
                "sale_type": "SERVICES"
            }
        ],
        "payment_mode": "BANK_TRANSFER",
        "auto_submit_fbr": True
    }
    inv_resp = test_client.post("/api/v1/external/invoices", headers=erp_headers, json=invoice_payload)
    assert inv_resp.status_code == 201
    inv_data = inv_resp.json()
    invoice_id = inv_data["invoice_id"]
    job_id = inv_data["submission_job_id"]

    # Verify Tax Calculations:
    # 2 * 50000 = 100,000; - 5000 discount = 95,000 taxable; * 18% = 17,100; total = 112,100
    assert float(inv_data["taxable_amount"]) == 95000.0
    assert float(inv_data["total_tax"]) == 17100.0
    assert float(inv_data["grand_total"]) == 112100.0

    # Step 4 & 5: Worker processes FBR submission job
    assert job_id is not None
    worker_res = submit_invoice_to_fbr_task(
        job_id=job_id,
        correlation_id="e2e-test-corr-1",
        tenant_id=e2e_env["tenant_id"]
    )
    assert worker_res["status"] == "ACCEPTED"
    assert worker_res["fbr_invoice_number"] is not None

    # Verify invoice status transitioned to VALID
    status_resp = test_client.get(f"/api/v1/external/invoices/{invoice_id}/status", headers=erp_headers)
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    assert st_data["fbr_status"] == "VALID"
    assert st_data["fbr_invoice_number"] == worker_res["fbr_invoice_number"]
    assert st_data["fbr_qr_data"] is not None

    # Step 6: Verify PDF generation & short-lived signed download URL
    pdf_resp = test_client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=admin_headers)
    assert pdf_resp.status_code == 200
    pdf_data = pdf_resp.json()
    assert "/documents/files/" in pdf_data["download_url"] or "token=" in pdf_data["download_url"]

    # Step 7: Issue Credit Note & test cumulative balance ceiling protection
    # Original grand total is 112,100. Attempting credit note of 153,400 must fail!
    cn_over_resp = test_client.post(
        "/api/v1/credit-notes",
        headers=admin_headers,
        json={
            "original_invoice_id": invoice_id,
            "reason": "Exorbitant credit test",
            "taxable_amount": 130000.0,
            "tax_amount": 23400.0,
            "grand_total": 153400.0,
        }
    )
    assert cn_over_resp.status_code == 400, "Credit note exceeding invoice grand total must be rejected"

    # Valid Credit Note within ceiling
    cn_valid_resp = test_client.post(
        "/api/v1/credit-notes",
        headers=admin_headers,
        json={
            "original_invoice_id": invoice_id,
            "reason": "Partial license discount adjustment",
            "taxable_amount": 10000.0,
            "tax_amount": 1800.0,
            "grand_total": 11800.0,
        }
    )
    assert cn_valid_resp.status_code in (200, 201)

    # Step 8: Strict Cross-Tenant Isolation Enforcement
    intruder_headers = {"Authorization": f"Bearer {e2e_env['intruder_token']}"}
    # Intruder tries to read invoice
    assert test_client.get(f"/api/v1/invoices/{invoice_id}", headers=intruder_headers).status_code == 404
    # Intruder tries to download PDF
    assert test_client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=intruder_headers).status_code == 404
    # Intruder tries to list webhook deliveries
    wh_deliveries = test_client.get("/api/v1/webhooks/deliveries", headers=intruder_headers).json()
    assert len(wh_deliveries) == 0
