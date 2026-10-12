from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.models.product import Product
from backend.app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, FBRSubmissionStatus
from backend.app.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceValidationResult
from backend.app.services.tax_engine import PakistanTaxEngine, TaxCalculationError
from backend.app.services.audit_service import AuditService
from backend.app.adapters.factory import FBRAdapterFactory


class InvoiceService:
    @staticmethod
    def generate_next_invoice_number(db: Session, tenant_id: str, branch_code: str) -> str:
        settings = db.query(OrganizationSettings).filter(
            OrganizationSettings.organization_id == tenant_id
        ).with_for_update().first()
        
        prefix = settings.invoice_prefix if settings else "INV"
        seq = settings.next_invoice_number if settings else 1001
        year = datetime.now(timezone.utc).year
        
        invoice_number = f"{prefix}-{branch_code}-{year}-{seq:05d}"
        
        if settings:
            settings.next_invoice_number = seq + 1
            db.commit()
            
        return invoice_number

    @classmethod
    def create_invoice(
        cls,
        db: Session,
        tenant_id: str,
        user_id: str,
        user_email: str,
        data: InvoiceCreate
    ) -> Invoice:
        # Verify branch belongs to tenant
        branch = db.query(Branch).filter(
            Branch.id == data.branch_id,
            Branch.tenant_id == tenant_id,
            Branch.is_active == True
        ).first()
        if not branch:
            raise HTTPException(status_code=400, detail="Invalid or inactive branch selected")

        # Verify customer belongs to tenant
        customer = db.query(Customer).filter(
            Customer.id == data.customer_id,
            Customer.tenant_id == tenant_id,
            Customer.is_active == True
        ).first()
        if not customer:
            raise HTTPException(status_code=400, detail="Invalid or inactive customer selected")

        # Fetch Taxpayer (Seller) details
        taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant_id).first()
        if not taxpayer:
            raise HTTPException(status_code=400, detail="Organization taxpayer profile not configured")

        if not data.items:
            raise HTTPException(status_code=400, detail="Invoice must contain at least one line item")

        # Calculate line items and totals
        raw_items_calc = []
        for itm in data.items:
            raw_items_calc.append({
                "quantity": itm.quantity,
                "unit_price": itm.unit_price,
                "discount": itm.discount,
                "tax_rate": itm.tax_rate
            })

        try:
            totals = PakistanTaxEngine.calculate_invoice_totals(raw_items_calc, data.other_charges)
        except TaxCalculationError as e:
            raise HTTPException(status_code=400, detail=str(e))

        invoice_num = cls.generate_next_invoice_number(db, tenant_id, branch.branch_code)

        invoice = Invoice(
            tenant_id=tenant_id,
            created_by=user_id,
            branch_id=branch.id,
            customer_id=customer.id,
            invoice_number=invoice_num,
            invoice_type=data.invoice_type,
            invoice_date=data.invoice_date or datetime.now(timezone.utc),
            due_date=data.due_date,
            
            # Seller Snapshot
            seller_name=taxpayer.legal_name,
            seller_ntn=taxpayer.ntn,
            seller_strn=taxpayer.strn,
            seller_branch_code=branch.branch_code,
            seller_province=branch.province,
            
            # Buyer Snapshot
            buyer_name=customer.name,
            buyer_ntn=customer.ntn,
            buyer_strn=customer.strn,
            buyer_cnic=customer.cnic,
            buyer_registration_type=customer.registration_type,
            buyer_address=customer.address,
            buyer_province=customer.province,
            
            # Financial Totals
            subtotal=totals["subtotal"],
            total_discount=totals["total_discount"],
            taxable_amount=totals["taxable_amount"],
            total_tax=totals["total_tax"],
            other_charges=totals["other_charges"],
            grand_total=totals["grand_total"],
            
            status=InvoiceStatus.DRAFT.value,
            fbr_status=FBRSubmissionStatus.NOT_SUBMITTED.value,
            reference_number=data.reference_number,
            payment_terms=data.payment_terms,
            notes=data.notes
        )
        db.add(invoice)
        db.flush()

        # Add line items
        for idx, itm in enumerate(data.items, 1):
            line_calc = PakistanTaxEngine.calculate_line_item(
                itm.quantity, itm.unit_price, itm.discount, itm.tax_rate
            )
            item_row = InvoiceItem(
                invoice_id=invoice.id,
                product_id=itm.product_id,
                item_seq=idx,
                item_code=itm.item_code,
                description=itm.description,
                hs_code=itm.hs_code,
                quantity=itm.quantity,
                uom=itm.uom,
                unit_price=itm.unit_price,
                gross_amount=line_calc["gross_amount"],
                discount=line_calc["discount"],
                taxable_amount=line_calc["taxable_amount"],
                tax_rate=itm.tax_rate,
                tax_amount=line_calc["tax_amount"],
                line_total=line_calc["line_total"],
                sale_type=itm.sale_type,
                sro_reference=itm.sro_reference
            )
            db.add(item_row)

        db.commit()
        db.refresh(invoice)

        AuditService.log(
            db=db,
            tenant_id=tenant_id,
            action="INVOICE_CREATE",
            entity="Invoice",
            entity_id=invoice.id,
            user_id=user_id,
            user_email=user_email,
            after_state={"invoice_number": invoice.invoice_number, "grand_total": str(invoice.grand_total)}
        )

        return invoice

    @classmethod
    def validate_invoice(cls, db: Session, invoice: Invoice) -> InvoiceValidationResult:
        errors = []
        warnings = []

        if not invoice.seller_ntn:
            errors.append("Taxpayer (Seller) NTN is missing")
        if not invoice.buyer_name:
            errors.append("Customer (Buyer) name is missing")
        if not invoice.items:
            errors.append("Invoice contains no line items")

        for idx, item in enumerate(invoice.items, 1):
            if not item.hs_code or len(item.hs_code.strip()) < 4:
                errors.append(f"Line {idx}: Valid Pakistan HS Code is required")
            if item.quantity <= 0:
                errors.append(f"Line {idx}: Quantity must be greater than zero")
            if item.unit_price < 0:
                errors.append(f"Line {idx}: Unit price cannot be negative")

        # Adapter validation
        settings = db.query(OrganizationSettings).filter(
            OrganizationSettings.organization_id == invoice.tenant_id
        ).first()
        fbr_mode = settings.fbr_mode if settings else "DEMO"
        adapter = FBRAdapterFactory.get_adapter(fbr_mode)
        
        adapter_res = adapter.validate_invoice({
            "seller_ntn": invoice.seller_ntn,
            "buyer_ntn": invoice.buyer_ntn,
            "invoice_number": invoice.invoice_number,
            "reference_number": invoice.reference_number,
            "notes": invoice.notes,
            "items": [{"hs_code": i.hs_code, "quantity": float(i.quantity), "tax_rate": float(i.tax_rate)} for i in invoice.items]
        })

        errors.extend(adapter_res.get("errors", []))
        warnings.extend(adapter_res.get("warnings", []))

        is_valid = len(errors) == 0
        if is_valid:
            invoice.status = InvoiceStatus.READY.value
        else:
            invoice.status = InvoiceStatus.INVALID.value
        db.commit()

        return InvoiceValidationResult(
            invoice_id=invoice.id,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            fbr_ready=is_valid
        )
