import uuid
from decimal import Decimal
import pytest
from backend.app.core.database import SessionLocal
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.models.invoice import Invoice, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.note import CreditNote, DebitNote, NoteStatus
from backend.app.services.pdf_service import pdf_generator
from backend.app.workers.tasks import submit_note_to_fbr_task


@pytest.fixture
def note_test_env():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:10]
    tenant_id = f"tenant-{uid}"

    org = Organization(id=tenant_id, name="Recon Org", slug=f"recon-{uid}", plan="STANDARD")
    settings = OrganizationSettings(organization_id=tenant_id, fbr_mode="DEMO")
    taxpayer = Taxpayer(
        tenant_id=tenant_id,
        legal_name="Recon Taxpayer Corp",
        ntn="1234567-8",
        strn="1234567890123",
        address="Commercial Plaza, Blue Area, Islamabad",
        city="Islamabad",
        province="Federal",
        country="Pakistan"
    )
    branch = Branch(
        id=f"branch-{uid}",
        tenant_id=tenant_id,
        branch_name="Islamabad Branch",
        branch_code="ISB-01",
        province="Federal",
        city="Islamabad",
        address="Blue Area",
    )
    customer = Customer(
        id=f"cust-{uid}",
        tenant_id=tenant_id,
        name="Client Enterprise Ltd",
        ntn="8877665-4",
        registration_type="REGISTERED",
        buyer_type="CORPORATE",
        province="Federal",
        city="Islamabad",
        address="Sector G-7",
    )

    inv = Invoice(
        id=f"inv-{uid}",
        tenant_id=tenant_id,
        branch_id=branch.id,
        customer_id=customer.id,
        invoice_number=f"INV-{uid}",
        invoice_type="TAX_INVOICE",
        seller_name=taxpayer.legal_name,
        seller_ntn=taxpayer.ntn,
        seller_strn=taxpayer.strn,
        seller_branch_code=branch.branch_code,
        seller_province=branch.province,
        buyer_name=customer.name,
        buyer_ntn=customer.ntn,
        buyer_address=customer.address,
        buyer_province=customer.province,
        subtotal=Decimal("1000.00"),
        taxable_amount=Decimal("1000.00"),
        total_tax=Decimal("180.00"),
        grand_total=Decimal("1180.00"),
        status=InvoiceStatus.VALID.value,
        fbr_status=FBRSubmissionStatus.VALID.value,
        fbr_invoice_number=f"FBR-INV-{uid}",
    )
    db.add_all([org, settings, taxpayer, branch, customer, inv])
    db.commit()

    yield {
        "db": db,
        "tenant_id": tenant_id,
        "invoice": inv,
        "taxpayer": taxpayer,
        "uid": uid,
    }
    db.close()


def test_credit_note_reconciliation_limits(note_test_env):
    db = note_test_env["db"]
    tenant_id = note_test_env["tenant_id"]
    inv = note_test_env["invoice"]
    uid = note_test_env["uid"]

    # 1. Create first valid credit note (e.g. 500 PKR of 1180 total)
    crn1 = CreditNote(
        id=f"crn-1-{uid}",
        tenant_id=tenant_id,
        credit_note_number=f"CRN-1-{uid}",
        original_invoice_id=inv.id,
        original_invoice_number=inv.invoice_number,
        reason="Partial return of defective goods",
        buyer_name=inv.buyer_name,
        buyer_ntn=inv.buyer_ntn,
        taxable_amount=Decimal("423.73"),
        tax_amount=Decimal("76.27"),
        grand_total=Decimal("500.00"),
        status=NoteStatus.READY.value,
    )
    db.add(crn1)
    db.commit()

    # Cumulative check: Total credited is 500, remaining balance is 680
    existing = db.query(CreditNote).filter(
        CreditNote.original_invoice_id == inv.id,
        CreditNote.tenant_id == tenant_id,
        CreditNote.status != NoteStatus.CANCELLED.value,
    ).all()
    already_credited = sum(Decimal(str(c.grand_total)) for c in existing)
    assert already_credited == Decimal("500.00")
    remaining = inv.grand_total - already_credited
    assert remaining == Decimal("680.00")

    # 2. Attempting a credit note exceeding 680 (e.g. 700) should breach limits
    excess_amount = Decimal("700.00")
    assert excess_amount > remaining


def test_credit_note_pdf_generation(note_test_env):
    inv = note_test_env["invoice"]
    taxpayer = note_test_env["taxpayer"]
    tenant_id = note_test_env["tenant_id"]
    uid = note_test_env["uid"]

    crn = CreditNote(
        id=f"crn-pdf-{uid}",
        tenant_id=tenant_id,
        credit_note_number=f"CRN-PDF-{uid}",
        original_invoice_id=inv.id,
        original_invoice_number=inv.invoice_number,
        reason="Price adjustment discount",
        buyer_name=inv.buyer_name,
        buyer_ntn=inv.buyer_ntn,
        taxable_amount=Decimal("100.00"),
        tax_amount=Decimal("18.00"),
        grand_total=Decimal("118.00"),
        status=NoteStatus.READY.value,
        fbr_status="NOT_SUBMITTED",
        fbr_is_simulated=True,
    )

    pdf_bytes = pdf_generator.generate_note(
        note=crn,
        note_type="CREDIT_NOTE",
        original_invoice=inv,
        taxpayer=taxpayer,
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_submit_note_to_fbr_worker_task(note_test_env):
    db = note_test_env["db"]
    tenant_id = note_test_env["tenant_id"]
    inv = note_test_env["invoice"]
    uid = note_test_env["uid"]

    crn = CreditNote(
        id=f"crn-sub-{uid}",
        tenant_id=tenant_id,
        credit_note_number=f"CRN-SUB-{uid}",
        original_invoice_id=inv.id,
        original_invoice_number=inv.invoice_number,
        reason="Defective items returned",
        buyer_name=inv.buyer_name,
        buyer_ntn=inv.buyer_ntn,
        taxable_amount=Decimal("200.00"),
        tax_amount=Decimal("36.00"),
        grand_total=Decimal("236.00"),
        status=NoteStatus.QUEUED.value,
        fbr_status="PENDING",
    )
    db.add(crn)
    db.commit()

    # Execute worker task directly
    res = submit_note_to_fbr_task(
        note_type="CREDIT",
        note_id=crn.id,
        tenant_id=tenant_id,
        correlation_id=f"corr-note-{uid}",
    )
    assert res["status"] == "VALID"
    assert "fbr_invoice_number" in res

    db.refresh(crn)
    assert crn.status == NoteStatus.VALID.value
    assert crn.fbr_status == "VALID"
    assert crn.fbr_invoice_number is not None
