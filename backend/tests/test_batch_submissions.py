import json
import uuid
from decimal import Decimal
import pytest
from backend.app.core.database import SessionLocal
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.document import BackgroundJob, BackgroundJobStatus
from backend.app.models.submission_job import InvoiceSubmissionJob, SubmissionJobStatus
from backend.app.models.base import now_utc
from backend.app.services.fbr_service import FBRService
from backend.app.workers.tasks import process_batch_fbr_submission_task


@pytest.fixture
def batch_test_env():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:10]
    tenant_id = f"tenant-{uid}"

    org = Organization(id=tenant_id, name="Batch Org", slug=f"batch-{uid}", plan="STANDARD")
    settings = OrganizationSettings(organization_id=tenant_id, fbr_mode="DEMO")
    branch = Branch(
        id=f"branch-{uid}",
        tenant_id=tenant_id,
        branch_name="Batch Branch",
        branch_code="BB-01",
        province="Sindh",
        city="Karachi",
        address="I.I. Chundrigar Road",
    )
    customer = Customer(
        id=f"cust-{uid}",
        tenant_id=tenant_id,
        name="Retail Client",
        ntn="7766554-3",
        registration_type="REGISTERED",
        buyer_type="CORPORATE",
        province="Sindh",
        city="Karachi",
        address="Clifton",
    )
    db.add_all([org, settings, branch, customer])
    db.commit()

    invoices = []
    for i in range(3):
        inv = Invoice(
            id=f"inv-{uid}-{i}",
            tenant_id=tenant_id,
            branch_id=branch.id,
            customer_id=customer.id,
            invoice_number=f"INV-BATCH-{uid}-{i}",
            invoice_type="TAX_INVOICE",
            seller_name="Batch Taxpayer",
            seller_ntn="1234567-8",
            seller_strn="1234567890123",
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
            status=InvoiceStatus.READY.value if i < 2 else InvoiceStatus.VALID.value,
            fbr_status=FBRSubmissionStatus.NOT_SUBMITTED.value if i < 2 else FBRSubmissionStatus.VALID.value,
        )
        item = InvoiceItem(
            item_seq=1,
            item_code="BATCH-ITM-01",
            description="Batch Test Commodity",
            hs_code="8471.30.10",
            quantity=Decimal("1.000"),
            uom="NOS",
            unit_price=Decimal("1000.00"),
            gross_amount=Decimal("1000.00"),
            discount=Decimal("0.00"),
            taxable_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            tax_amount=Decimal("180.00"),
            line_total=Decimal("1180.00"),
            sale_type="GOODS",
        )
        inv.items = [item]
        db.add(inv)
        invoices.append(inv)
    db.commit()

    yield {
        "db": db,
        "tenant_id": tenant_id,
        "invoices": invoices,
        "uid": uid,
    }
    db.close()


def test_batch_submission_queue_and_worker(batch_test_env):
    db = batch_test_env["db"]
    tenant_id = batch_test_env["tenant_id"]
    invoices = batch_test_env["invoices"]
    uid = batch_test_env["uid"]

    # Invoices 0 and 1 are READY; Invoice 2 is already VALID
    eligible = [inv for inv in invoices if inv.status != InvoiceStatus.VALID.value]
    assert len(eligible) == 2

    # Create Batch background job
    correlation_id = f"batch-corr-{uid}"
    bg_job = BackgroundJob(
        id=f"bg-{uid}",
        tenant_id=tenant_id,
        job_type="BATCH_FBR_SUBMISSION",
        entity_type="BATCH",
        status=BackgroundJobStatus.QUEUED.value,
        correlation_id=correlation_id,
        enqueued_at=now_utc(),
        params=json.dumps({"total": len(eligible), "invoice_ids": [inv.id for inv in eligible]}),
    )
    db.add(bg_job)
    db.commit()

    # Create submission jobs linked to batch
    for inv in eligible:
        FBRService.queue_invoice_submission(
            db=db,
            invoice=inv,
            user_id="test-user",
            user_email="test@example.com",
            forced_scenario="VALID",
            batch_job_id=bg_job.id,
            auto_dispatch=False,
        )

    # Process batch via worker task
    res = process_batch_fbr_submission_task(
        batch_job_id=bg_job.id,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
    )
    assert res["total"] == 2
    assert res["succeeded"] == 2
    assert res["failed"] == 0

    db.refresh(bg_job)
    assert bg_job.status == BackgroundJobStatus.COMPLETED.value
    params = json.loads(bg_job.params)
    assert params["succeeded"] == 2

    # Check each individual job
    jobs = db.query(InvoiceSubmissionJob).filter(InvoiceSubmissionJob.batch_job_id == bg_job.id).all()
    assert len(jobs) == 2
    for j in jobs:
        assert j.status == SubmissionJobStatus.ACCEPTED.value
