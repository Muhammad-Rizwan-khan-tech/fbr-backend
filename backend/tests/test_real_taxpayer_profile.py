"""Regression tests for real client taxpayer profile and PRAL seller snapshot."""
import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, SessionLocal, engine
from backend.app.core.fbr_taxpayer import normalize_seller_tax_id, is_incomplete_tax_profile
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.tenant import OrganizationSettings
from backend.app.models.fbr_credential import FBRCredential
from backend.app.models.invoice import Invoice, InvoiceItem
from backend.app.models.customer import Customer
from backend.app.services.fbr_service import FBRService


def test_ntn_format_validation_is_lossless_and_strict():
    assert normalize_seller_tax_id("7654321") == "7654321"
    assert normalize_seller_tax_id("7654321-9") == "7654321"
    assert normalize_seller_tax_id("76543219") == "7654321"  # contiguous check digit
    assert normalize_seller_tax_id("42101-1234567-1") == "4210112345671"
    assert normalize_seller_tax_id(None) == ""
    for invalid in ["123", "765432199", "76543INVALID"]:
        with pytest.raises(ValueError):
            normalize_seller_tax_id(invalid)
    assert is_incomplete_tax_profile("1000000-0", "Pakistan", "Punjab")
    assert is_incomplete_tax_profile("", "", "")
    assert not is_incomplete_tax_profile("7654321", "Plot 4, Hyderabad", "Sindh")


def test_create_and_update_admin_client_persists_real_taxpayer_values():
    Base.metadata.create_all(bind=engine)
    cli = TestClient(app)
    headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    suffix = uuid.uuid4().hex[:8]
    response = cli.post("/api/v1/admin/clients", headers=headers, json={
        "company_name": f"Tax Profile Integration {suffix}",
        "username": f"taxprofile_{suffix}",
        "fbr_api_token": "test-token-local-only",
        "ntn": "76543219",
        "strn": "123456789",
        "province": "Sindh",
        "city": "Hyderabad",
        "address": "Plot 22 Auto Bhan Road Hyderabad",
        "fbr_pos_id": "POS-123",
        "business_activity": "WHOLESALER",
    })
    assert response.status_code == 200, response.text
    oid = response.json()["organization_id"]
    db = SessionLocal()
    try:
        tp = db.query(Taxpayer).filter(Taxpayer.tenant_id == oid).one()
        branch = db.query(Branch).filter(Branch.tenant_id == oid, Branch.is_main.is_(True)).one()
        cred = db.query(FBRCredential).filter(FBRCredential.organization_id == oid).one()
        orgs = db.query(OrganizationSettings).filter(OrganizationSettings.organization_id == oid).one()
        assert tp.ntn == "7654321"
        assert tp.province == "Sindh"
        assert branch.address == "Plot 22 Auto Bhan Road Hyderabad"
        assert cred.fbr_pos_id == "POS-123"
        assert orgs.fbr_pos_id == "POS-123"
        detail = cli.get(f"/api/v1/admin/clients/{oid}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["tax_profile_complete"] is True
        assert detail.json()["ntn"] == "7654321"

        updated = cli.patch(f"/api/v1/admin/clients/{oid}", headers=headers, json={
            "ntn": "12345678",
            "address": "New tax address 42, Latifabad, Hyderabad",
            "province": "Sindh",
            "city": "Hyderabad",
            "fbr_pos_id": "POS-987",
        })
        assert updated.status_code == 200, updated.text
        db.expire_all()
        assert db.query(Taxpayer).filter(Taxpayer.tenant_id == oid).one().ntn == "1234567"
        assert db.query(Branch).filter(Branch.tenant_id == oid, Branch.is_main.is_(True)).one().address.startswith("New tax address")
        assert db.query(FBRCredential).filter(FBRCredential.organization_id == oid).one().fbr_pos_id == "POS-987"

        invalid = cli.patch(f"/api/v1/admin/clients/{oid}", headers=headers, json={"ntn": "not-an-ntn"})
        assert invalid.status_code == 422

        # Uploaded cloud ZIP's end-to-end seller profile expectation:
        # invoice JSON must use the corrected taxpayer identity and main branch
        # after create + edit, without posting an invoice to the FBR gateway.
        buyer = Customer(
            tenant_id=oid, name="Test Buyer", ntn="1122334",
            registration_type="REGISTERED", address="Lahore",
            city="Lahore", province="Punjab",
        )
        db.add(buyer)
        db.flush()
        current_taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == oid).one()
        current_branch = db.query(Branch).filter(
            Branch.tenant_id == oid, Branch.is_main.is_(True)
        ).one()
        draft = Invoice(
            tenant_id=oid, branch_id=current_branch.id, customer_id=buyer.id,
            invoice_number="NTN-PAYLOAD-" + suffix, invoice_type="TAX_INVOICE",
            seller_name=current_taxpayer.legal_name, seller_ntn=current_taxpayer.ntn,
            seller_strn=current_taxpayer.strn, seller_branch_code=current_branch.branch_code,
            seller_province=current_branch.province, buyer_name=buyer.name,
            buyer_ntn=buyer.ntn, buyer_registration_type="REGISTERED",
            buyer_address=buyer.address, buyer_province=buyer.province,
            subtotal=Decimal("1000.00"), total_discount=Decimal("0.00"),
            taxable_amount=Decimal("1000.00"), total_tax=Decimal("180.00"),
            other_charges=Decimal("0.00"), grand_total=Decimal("1180.00"),
        )
        db.add(draft)
        db.flush()
        item = InvoiceItem(
            invoice_id=draft.id, item_seq=1, item_code="ITM-01",
            description="Test taxable goods", hs_code="8471.30.10",
            quantity=Decimal("1.00"), uom="Numbers",
            unit_price=Decimal("1000.00"), gross_amount=Decimal("1000.00"),
            taxable_amount=Decimal("1000.00"), tax_rate=Decimal("18.00"),
            tax_amount=Decimal("180.00"), line_total=Decimal("1180.00"),
            sale_type="STANDARD",
        )
        db.add(item)
        db.commit()
        db.refresh(draft)
        payload = FBRService._build_fbr_payload(draft, db=db)
        assert payload["sellerNTNCNIC"] == "1234567"
        assert payload["sellerProvince"] == "Sindh"
        assert payload["sellerAddress"] == "New tax address 42, Latifabad, Hyderabad"
        assert payload["sellerBusinessName"] == current_taxpayer.legal_name
        assert payload["items"][0]["hsCode"] == "8471.30.10"

    finally:
        db.close()


def test_invoice_seller_id_normalization_preserves_real_details():
    invoice = Invoice(
        invoice_number="TEST-SNAPSHOT",
        invoice_type="STANDARD",
        seller_ntn="7654321-9",
        seller_name="Test Org",
        seller_province="Sindh",
        seller_branch_code="MAIN",
        buyer_name="Buyer",
        buyer_registration_type="Unregistered",
        buyer_province="Sindh",
        buyer_address="Hyderabad",
        subtotal=0, total_discount=0, taxable_amount=0,
        total_tax=0, other_charges=0, grand_total=0,
    )
    invoice.items = []
    payload = FBRService._build_fbr_payload(invoice)
    assert payload["sellerNTNCNIC"] == "7654321"
    assert payload["sellerProvince"] == "Sindh"
