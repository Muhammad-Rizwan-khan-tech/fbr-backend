"""Mutable invoice lifecycle with tenant-scoped, audit-preserving removal."""
from decimal import Decimal
from fastapi import HTTPException
from backend.app.models.invoice import Invoice, InvoiceItem
from backend.app.models.fbr import FBRSubmission
from backend.app.models.submission_job import InvoiceSubmissionJob
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.models.taxpayer import Taxpayer
from backend.app.schemas.invoice import InvoiceItemCreate
from backend.app.services.tax_engine import PakistanTaxEngine, TaxCalculationError
from backend.app.services.audit_service import AuditService

ACTIVE = ("QUEUED", "PROCESSING", "SUBMITTING", "RETRYING", "PENDING", "SUBMITTED", "VALIDATING", "ACCEPTED")


def load_mutable(db, tenant_id, invoice_id, deleting=False):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id).with_for_update().first()
    if not inv or inv.status == "DELETED":
        raise HTTPException(404, "Invoice not found")
    accepted = db.query(FBRSubmission.id).filter(FBRSubmission.invoice_id == inv.id, FBRSubmission.tenant_id == tenant_id, FBRSubmission.status == "VALID").first()
    if inv.status == "VALID" or inv.fbr_status == "VALID" or inv.fbr_invoice_number or accepted:
        raise HTTPException(400, "Accepted FBR invoices cannot be edited or removed. Use a Credit or Debit Note.")
    active_job = db.query(InvoiceSubmissionJob.id).filter(InvoiceSubmissionJob.invoice_id == inv.id, InvoiceSubmissionJob.tenant_id == tenant_id, InvoiceSubmissionJob.status.in_(ACTIVE)).first()
    if inv.status in ACTIVE or inv.fbr_status == "PENDING" or active_job:
        raise HTTPException(409, "Invoice submission is in flight. Wait for its final result.")
    if inv.status == "CANCELLED" and not deleting:
        raise HTTPException(400, "Cancelled invoices cannot be edited or resubmitted")
    return inv


def update_invoice(db, tenant_id, invoice_id, data, user):
    inv = load_mutable(db, tenant_id, invoice_id)
    fields = data.model_dump(exclude_unset=True)
    branch_id = fields.get("branch_id") or inv.branch_id
    customer_id = fields.get("customer_id") or inv.customer_id
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.tenant_id == tenant_id, Branch.is_active.is_(True)).first()
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == tenant_id, Customer.is_active.is_(True)).first()
    taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant_id).first()
    if not branch or not customer or not taxpayer:
        raise HTTPException(400, "Active tenant branch, customer and seller profile are required")
    items = data.items if "items" in fields else [InvoiceItemCreate.model_validate(x, from_attributes=True) for x in inv.items]
    if not items:
        raise HTTPException(422, "At least one invoice item is required")
    charges = fields.get("other_charges") if fields.get("other_charges") is not None else inv.other_charges
    try:
        totals = PakistanTaxEngine.calculate_invoice_totals([x.model_dump() for x in items], charges)
    except (TaxCalculationError, ArithmeticError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from None
    new_items = []
    additional = Decimal("0")
    for idx, item in enumerate(items, 1):
        calc = PakistanTaxEngine.calculate_line_item(item.quantity, item.unit_price, item.discount, item.tax_rate)
        extra = sum((item.extra_tax, item.further_tax, item.fed_payable), Decimal("0"))
        for amount in (item.extra_tax, item.further_tax, item.fed_payable, item.sales_tax_withheld_at_source, item.fixed_notified_value_or_retail_price):
            if not amount.is_finite() or amount < 0:
                raise HTTPException(422, "Invoice tax amounts must be finite, non-negative numbers")
        if item.product_id:
            from backend.app.models.product import Product
            if not db.query(Product.id).filter(Product.id == item.product_id, Product.tenant_id == tenant_id).first():
                raise HTTPException(400, "Product does not belong to this organization")
        raw = item.model_dump(exclude={"quantity", "unit_price", "discount"})
        new_items.append(InvoiceItem(**raw, item_seq=idx, quantity=item.quantity, unit_price=item.unit_price,
            discount=calc["discount"], gross_amount=calc["gross_amount"], taxable_amount=calc["taxable_amount"],
            tax_amount=calc["tax_amount"], line_total=calc["line_total"] + extra))
        additional += extra
    before = {"status": inv.status, "grand_total": str(inv.grand_total)}
    inv.branch_id, inv.customer_id = branch_id, customer_id
    inv.seller_name, inv.seller_ntn, inv.seller_strn = taxpayer.legal_name, taxpayer.ntn, taxpayer.strn
    inv.seller_branch_code, inv.seller_province = branch.branch_code, branch.province
    if "customer_id" in fields:
        for key, value in {"buyer_name":customer.name,"buyer_ntn":customer.ntn,"buyer_cnic":customer.cnic,"buyer_strn":customer.strn,"buyer_registration_type":customer.registration_type,"buyer_address":customer.address,"buyer_province":customer.province}.items():
            setattr(inv, key, value)
    for key in ("invoice_type", "invoice_date", "due_date", "reference_number", "scenario_id", "payment_terms", "notes", "buyer_name", "buyer_ntn", "buyer_cnic", "buyer_address", "buyer_province", "buyer_registration_type"):
        if key in fields:
            if key in ("buyer_name", "buyer_address", "buyer_province", "invoice_type", "invoice_date", "buyer_registration_type") and not fields[key]:
                raise HTTPException(422, key + " cannot be empty")
            setattr(inv, key, fields[key])
    inv.items = new_items
    for key in ("subtotal", "total_discount", "taxable_amount", "total_tax", "other_charges", "grand_total"):
        setattr(inv, key, totals[key])
    inv.total_tax += additional
    inv.grand_total += additional
    inv.status, inv.fbr_status = "DRAFT", "NOT_SUBMITTED"
    inv.fbr_error_code = inv.fbr_error_message = None
    inv.fbr_qr_data = inv.fbr_submission_date = None
    db.commit()
    db.refresh(inv)
    AuditService.log(db=db, tenant_id=tenant_id, action="INVOICE_EDIT", entity="Invoice", entity_id=inv.id, user_id=user.id, user_email=user.email, before_state=before, after_state={"status":"DRAFT", "grand_total":str(inv.grand_total)})
    return inv


def remove_invoice(db, tenant_id, invoice_id, user):
    inv = load_mutable(db, tenant_id, invoice_id, deleting=True)
    previous = inv.status
    inv.status = "DELETED"
    db.commit()
    AuditService.log(db=db, tenant_id=tenant_id, action="INVOICE_REMOVE", entity="Invoice", entity_id=inv.id, user_id=user.id, user_email=user.email, before_state={"status":previous}, after_state={"status":"DELETED", "audit_history_retained":True})
    return {"success":True, "message":"Invoice removed from active views; audit history retained."}
