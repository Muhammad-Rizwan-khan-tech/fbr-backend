import datetime
from decimal import Decimal
import pytest

from backend.app.core.database import SessionLocal
from backend.app.core.errors import ConflictError
from backend.app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.submission_job import InvoiceSubmissionJob, SubmissionJobStatus
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.services.fbr_service import FBRService
from backend.app.workers.tasks import submit_invoice_to_fbr_task


import uuid


from backend.app.core.config import settings


@pytest.fixture
def test_setup():
    orig_inline = settings.QUEUE_INLINE_EXECUTION
    settings.QUEUE_INLINE_EXECUTION = "manual"
    db = SessionLocal()
    uid = uuid.uuid4().hex[:12]
    tenant_id = f"tenant-{uid}"

    # Setup organization and settings
    org = Organization(id=tenant_id, name="Test Async Org", slug=f"org-{uid}", plan="STANDARD")
    org_settings = OrganizationSettings(organization_id=tenant_id, fbr_mode="DEMO")
    branch = Branch(
        id=f"branch-{uid}",
        tenant_id=tenant_id,
        branch_name="Main Branch",
        branch_code="01",
        province="Punjab",
        city="Lahore",
        address="123 Tech Ave",
    )
    customer = Customer(
        id=f"cust-{uid}",
        tenant_id=tenant_id,
        name="Test Customer Ltd",
        ntn="1122334-5",
        registration_type="REGISTERED",
        buyer_type="CORPORATE",
        province="Punjab",
        city="Lahore",
        address="Commercial Market",
    )
    db.add_all([org, org_settings, branch, customer])
    db.commit()

    # Create Invoice
    invoice = Invoice(
        id=f"inv-{uid}",
        tenant_id=tenant_id,
        branch_id=branch.id,
        customer_id=customer.id,
        invoice_number=f"INV-ASYNC-{uid}",
        seller_name="Test Async Org",
        seller_ntn="7766554-3",
        seller_strn="3277876543210",
        seller_branch_code="01",
        seller_province="Punjab",
        buyer_name="Test Customer Ltd",
        buyer_ntn="1122334-5",
        buyer_registration_type="REGISTERED",
        buyer_province="Punjab",
        buyer_address="Commercial Market",
        subtotal=Decimal("20000.00"),
        total_discount=Decimal("0.00"),
        taxable_amount=Decimal("20000.00"),
        total_tax=Decimal("3600.00"),
        other_charges=Decimal("0.00"),
        grand_total=Decimal("23600.00"),
        status=InvoiceStatus.READY.value,
        fbr_status=FBRSubmissionStatus.NOT_SUBMITTED.value,
    )
    item = InvoiceItem(
        item_seq=1,
        item_code="PROD-ASYNC-1",
        description="Async Processing Test Item",
        hs_code="8471.30.10",
        quantity=Decimal("1.00"),
        uom="NOS",
        unit_price=Decimal("20000.00"),
        gross_amount=Decimal("20000.00"),
        discount=Decimal("0.00"),
        taxable_amount=Decimal("20000.00"),
        tax_rate=Decimal("18.00"),
        tax_amount=Decimal("3600.00"),
        line_total=Decimal("23600.00"),
        sale_type="GOODS",
    )
    invoice.items = [item]
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    yield db, invoice, tenant_id

    db.close()
    settings.QUEUE_INLINE_EXECUTION = orig_inline


def test_idempotent_queueing(test_setup):
    db, invoice, tenant_id = test_setup
    idem_key = "idemp-test-key-999"

    # 1. First queue call
    job1 = FBRService.queue_invoice_submission(
        db=db,
        invoice=invoice,
        user_id="user-1",
        user_email="user@test.com",
        idempotency_key=idem_key,
        forced_scenario="VALID",
    )
    assert job1.status == SubmissionJobStatus.QUEUED.value
    assert job1.is_simulated is True
    assert job1.provider == "MOCK"
    assert invoice.status == InvoiceStatus.QUEUED.value

    # 2. Second queue call with same Idempotency-Key
    job2 = FBRService.queue_invoice_submission(
        db=db,
        invoice=invoice,
        user_id="user-1",
        user_email="user@test.com",
        idempotency_key=idem_key,
        forced_scenario="VALID",
    )
    # Must return identical job without duplicating
    assert job2.id == job1.id


def test_worker_success_workflow(test_setup):
    db, invoice, tenant_id = test_setup

    job = FBRService.queue_invoice_submission(
        db=db,
        invoice=invoice,
        user_id="user-1",
        user_email="user@test.com",
        forced_scenario="VALID",
    )

    # Execute worker task synchronously
    res = submit_invoice_to_fbr_task(
        job_id=job.id, correlation_id=job.correlation_id, tenant_id=tenant_id
    )
    assert res["status"] == "ACCEPTED"
    assert "fbr_invoice_number" in res

    db.refresh(job)
    db.refresh(invoice)
    assert job.status == SubmissionJobStatus.ACCEPTED.value
    assert invoice.status == InvoiceStatus.VALID.value
    assert invoice.fbr_status == FBRSubmissionStatus.VALID.value
    assert invoice.fbr_invoice_number is not None
    assert invoice.fbr_is_simulated is True
    assert invoice.fbr_provider == "MOCK"


def test_worker_transient_retry_workflow(test_setup):
    db, invoice, tenant_id = test_setup

    job = FBRService.queue_invoice_submission(
        db=db,
        invoice=invoice,
        user_id="user-1",
        user_email="user@test.com",
        forced_scenario="TIMEOUT",
    )

    # First attempt fails with transient error -> RETRYING
    res = submit_invoice_to_fbr_task(
        job_id=job.id, correlation_id=job.correlation_id, tenant_id=tenant_id
    )
    assert res["status"] == "RETRYING"
    assert res["attempt"] == 1
    assert res["next_retry_in_seconds"] > 0

    db.refresh(job)
    db.refresh(invoice)
    assert job.status == SubmissionJobStatus.RETRYING.value
    assert invoice.status == InvoiceStatus.RETRYING.value
    assert job.attempt_count == 1
    assert job.next_retry_at is not None


def test_worker_permanent_rejection_workflow(test_setup):
    db, invoice, tenant_id = test_setup

    job = FBRService.queue_invoice_submission(
        db=db,
        invoice=invoice,
        user_id="user-1",
        user_email="user@test.com",
        forced_scenario="REJECTION",
    )

    # Permanent business rejection -> REJECTED (no retry)
    res = submit_invoice_to_fbr_task(
        job_id=job.id, correlation_id=job.correlation_id, tenant_id=tenant_id
    )
    assert res["status"] == "REJECTED"

    db.refresh(job)
    db.refresh(invoice)
    assert job.status == SubmissionJobStatus.REJECTED.value
    assert invoice.status == InvoiceStatus.REJECTED.value
    assert invoice.fbr_status == FBRSubmissionStatus.INVALID.value
