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
from backend.app.services.fbr_service import FBRService
from backend.app.adapters.factory import FBRAdapterFactory
from backend.app.adapters.production_adapter import ProductionFBRAdapter
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.models.fbr_credential import FBRCredential
from backend.app.core.pral_error_codes import lookup_pral_error


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
            Branch.is_active == True  # noqa: E712
        ).first()
        if not branch:
            raise HTTPException(status_code=400, detail="Invalid or inactive branch selected")

        # Verify customer belongs to tenant
        customer = db.query(Customer).filter(
            Customer.id == data.customer_id,
            Customer.tenant_id == tenant_id,
            Customer.is_active == True  # noqa: E712
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
            scenario_id=data.scenario_id,
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
            extra_tax_val = Decimal(str(itm.extra_tax or 0))
            further_tax_val = Decimal(str(itm.further_tax or 0))
            fed_payable_val = Decimal(str(itm.fed_payable or 0))
            additional_taxes = extra_tax_val + further_tax_val + fed_payable_val
            adjusted_line_total = line_calc["line_total"] + additional_taxes

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
                rate_desc=itm.rate_desc,
                tax_amount=line_calc["tax_amount"],
                fixed_notified_value_or_retail_price=itm.fixed_notified_value_or_retail_price,
                sales_tax_withheld_at_source=itm.sales_tax_withheld_at_source,
                extra_tax=extra_tax_val,
                further_tax=further_tax_val,
                fed_payable=fed_payable_val,
                line_total=adjusted_line_total,
                sale_type=itm.sale_type,
                sro_reference=itm.sro_reference,
                sro_item_serial_no=itm.sro_item_serial_no,
            )
            db.add(item_row)
            if additional_taxes > 0:
                invoice.total_tax = Decimal(str(invoice.total_tax)) + additional_taxes
                invoice.grand_total = Decimal(str(invoice.grand_total)) + additional_taxes

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
    def serialize_invoice_to_fbr_v112(
        cls,
        db: Session,
        invoice: Invoice,
        environment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Serialize a persisted Invoice into the exact PRAL DI API v1.12 Section 4.1 JSON schema."""
        canonical = FBRService._build_fbr_payload(invoice, db=db)
        env_upper = (environment or "").upper()
        if not env_upper:
            org_settings = db.query(OrganizationSettings).filter(
                OrganizationSettings.organization_id == invoice.tenant_id
            ).first()
            env_upper = (org_settings.fbr_mode if org_settings else "PRODUCTION").upper()
        if env_upper == "SANDBOX" or getattr(invoice, "scenario_id", None):
            return SandboxFBRAdapter()._transform_to_fbr_schema(canonical)
        return ProductionFBRAdapter()._transform_to_fbr_schema(canonical)

    @classmethod
    def serialize_draft_to_fbr_v112(
        cls,
        db: Session,
        tenant_id: str,
        data: InvoiceCreate,
        environment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Serialize an unsaved draft InvoiceCreate into the exact PRAL DI API v1.12 Section 4.1 JSON schema."""
        taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant_id).first()
        branch = db.query(Branch).filter(Branch.id == data.branch_id, Branch.tenant_id == tenant_id).first()
        customer = db.query(Customer).filter(Customer.id == data.customer_id, Customer.tenant_id == tenant_id).first()

        seller_province = branch.province if branch else (taxpayer.province if taxpayer else "Sindh")
        seller_address = (
            (branch.address if branch and branch.address else None)
            or (taxpayer.address if taxpayer and taxpayer.address else None)
            or f"{seller_province}, Pakistan"
        )
        buyer_reg = "Registered"
        if customer:
            is_reg = (
                str(customer.buyer_type).upper() in ("REGISTERED", "REGISTERED_BUSINESS")
                or str(customer.registration_type).upper() == "REGISTERED"
            )
            buyer_reg = "Registered" if is_reg else "Unregistered"

        items_list = []
        for idx, itm in enumerate(data.items, 1):
            try:
                line_calc = PakistanTaxEngine.calculate_line_item(
                    itm.quantity, itm.unit_price, itm.discount, itm.tax_rate
                )
            except Exception:
                line_calc = {
                    "gross_amount": Decimal("0.00"),
                    "discount": Decimal("0.00"),
                    "taxable_amount": Decimal("0.00"),
                    "tax_amount": Decimal("0.00"),
                    "line_total": Decimal("0.00"),
                }
            extra_tax_val = float(itm.extra_tax or 0)
            further_tax_val = float(itm.further_tax or 0)
            fed_payable_val = float(itm.fed_payable or 0)
            line_tot = float(line_calc["line_total"]) + extra_tax_val + further_tax_val + fed_payable_val
            rate_str = (
                itm.rate_desc.strip()
                if itm.rate_desc and itm.rate_desc.strip()
                else (f"{int(itm.tax_rate)}%" if float(itm.tax_rate).is_integer() else f"{float(itm.tax_rate)}%")
            )
            items_list.append({
                "item_seq": idx,
                "hs_code": itm.hs_code,
                "description": itm.description,
                "rate": rate_str,
                "tax_rate": float(itm.tax_rate),
                "uom": itm.uom,
                "quantity": float(itm.quantity),
                "unit_price": float(itm.unit_price),
                "discount": float(itm.discount or 0),
                "taxable_amount": float(line_calc["taxable_amount"]),
                "tax_amount": float(line_calc["tax_amount"]),
                "line_total": line_tot,
                "fixedNotifiedValueOrRetailPrice": float(itm.fixed_notified_value_or_retail_price or 0),
                "salesTaxWithheldAtSource": float(itm.sales_tax_withheld_at_source or 0),
                "extraTax": extra_tax_val,
                "furtherTax": further_tax_val,
                "fedPayable": fed_payable_val,
                "sale_type": itm.sale_type,
                "sro_reference": itm.sro_reference,
                "sro_item_serial_no": itm.sro_item_serial_no,
            })

        draft_dict = {
            "invoice_type": data.invoice_type,
            "invoice_date": (data.invoice_date or datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
            "seller_ntn": taxpayer.ntn if taxpayer else "",
            "seller_name": taxpayer.legal_name if taxpayer else "",
            "seller_province": seller_province,
            "seller_address": seller_address,
            "buyer_ntn": (customer.ntn or customer.cnic) if customer else "",
            "buyer_name": customer.name if customer else "",
            "buyer_province": customer.province if customer else seller_province,
            "buyer_address": customer.address if customer else "",
            "buyer_registration_type": buyer_reg,
            "reference_number": data.reference_number,
            "scenario_id": data.scenario_id,
            "items": items_list,
        }

        env_upper = (environment or "").upper()
        if env_upper == "SANDBOX" or data.scenario_id:
            return SandboxFBRAdapter()._transform_to_fbr_schema(draft_dict)
        return ProductionFBRAdapter()._transform_to_fbr_schema(draft_dict)

    @classmethod
    def validate_invoice(cls, db: Session, invoice: Invoice) -> InvoiceValidationResult:
        errors = []
        warnings = []
        line_item_errors = []
        structured_errors = []

        if not invoice.seller_ntn:
            err_meta = lookup_pral_error("0101")
            errors.append("[0101] Taxpayer (Seller) NTN is missing")
            if err_meta:
                structured_errors.append(err_meta.to_dict())

        if not invoice.buyer_name:
            errors.append("Customer (Buyer) name is missing")

        is_registered = str(invoice.buyer_registration_type).upper() in ("REGISTERED", "REGISTERED_BUSINESS")
        if is_registered and not invoice.buyer_ntn and not invoice.buyer_cnic:
            err_meta = lookup_pral_error("0103")
            errors.append("[0103] Buyer NTN/CNIC is required for Registered Buyer")
            if err_meta:
                structured_errors.append(err_meta.to_dict())

        is_debit = "DEBIT" in str(invoice.invoice_type).upper()
        if is_debit and not invoice.reference_number:
            err_meta = lookup_pral_error("0003")
            errors.append("[0003] Missing Reference Invoice Number for Debit Note")
            if err_meta:
                structured_errors.append(err_meta.to_dict())

        if not invoice.items:
            errors.append("Invoice contains no line items")

        for idx, item in enumerate(invoice.items, 1):
            if not item.hs_code or len(item.hs_code.strip()) < 4:
                err_meta = lookup_pral_error("0201")
                msg = f"Line {idx}: Valid Pakistan HS Code is required"
                errors.append(f"[0201] {msg}")
                line_item_errors.append({"item_seq": idx, "field": "hsCode", "error_code": "0201", "message": msg})
                if err_meta:
                    structured_errors.append(err_meta.to_dict())

            if item.quantity <= 0:
                err_meta = lookup_pral_error("0204")
                msg = f"Line {idx}: Quantity must be greater than zero"
                errors.append(f"[0204] {msg}")
                line_item_errors.append({"item_seq": idx, "field": "quantity", "error_code": "0204", "message": msg})
                if err_meta:
                    structured_errors.append(err_meta.to_dict())

            if item.unit_price < 0:
                msg = f"Line {idx}: Unit price cannot be negative"
                errors.append(msg)
                line_item_errors.append({"item_seq": idx, "field": "unit_price", "error_code": "0301", "message": msg})

        # Adapter validation
        settings = db.query(OrganizationSettings).filter(
            OrganizationSettings.organization_id == invoice.tenant_id
        ).first()
        cred = db.query(FBRCredential).filter(
            FBRCredential.organization_id == invoice.tenant_id
        ).first()
        adapter = FBRAdapterFactory.get_adapter_for_tenant(credential=cred, tenant_settings=settings)

        # Local validation, preview and submission must use one complete payload.
        from backend.app.services.fbr_service import FBRService
        adapter_res = adapter.validate_invoice(FBRService._build_fbr_payload(invoice, db=db))

        errors.extend(adapter_res.get("errors", []))
        warnings.extend(adapter_res.get("warnings", []))

        serialized = cls.serialize_invoice_to_fbr_v112(db, invoice)

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
            line_item_errors=line_item_errors,
            structured_errors=structured_errors,
            pral_status="Valid" if is_valid else "Invalid",
            fbr_ready=is_valid,
            official_live_verified=False,
            serialized_fbr_payload=serialized,
        )

    @classmethod
    def validate_draft_invoice(
        cls,
        db: Session,
        tenant_id: str,
        data: InvoiceCreate,
    ) -> InvoiceValidationResult:
        """Validates an unsaved draft invoice against PRAL rules without persisting to database."""
        from backend.app.core.fbr_extra_tax import reduced_extra_tax_errors
        errors = reduced_extra_tax_errors(data.items)
        warnings = []
        line_item_errors = []
        structured_errors = []

        taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant_id).first()
        if not taxpayer or not taxpayer.ntn:
            err_meta = lookup_pral_error("0101")
            errors.append("[0101] Taxpayer (Seller) NTN is not configured in organization settings")
            if err_meta:
                structured_errors.append(err_meta.to_dict())

        customer = db.query(Customer).filter(
            Customer.id == data.customer_id,
            Customer.tenant_id == tenant_id
        ).first()
        if not customer:
            errors.append("Selected customer not found")
        else:
            is_registered = str(customer.buyer_type).upper() in ("REGISTERED", "REGISTERED_BUSINESS") or str(customer.registration_type).upper() == "REGISTERED"
            if is_registered and not customer.ntn and not customer.cnic:
                err_meta = lookup_pral_error("0103")
                errors.append("[0103] Customer is marked Registered but lacks NTN or CNIC")
                if err_meta:
                    structured_errors.append(err_meta.to_dict())

        is_debit = "DEBIT" in str(data.invoice_type).upper()
        if is_debit and not data.reference_number:
            err_meta = lookup_pral_error("0003")
            errors.append("[0003] Missing original invoice reference (reference_number) for Debit Note")
            if err_meta:
                structured_errors.append(err_meta.to_dict())

        if not data.items:
            errors.append("Invoice must contain at least one line item")

        for idx, item in enumerate(data.items, 1):
            if not item.hs_code or len(item.hs_code.strip()) < 4:
                err_meta = lookup_pral_error("0201")
                msg = f"Line {idx}: Valid Pakistan HS Code is required"
                errors.append(f"[0201] {msg}")
                line_item_errors.append({"item_seq": idx, "field": "hsCode", "error_code": "0201", "message": msg})
                if err_meta:
                    structured_errors.append(err_meta.to_dict())

            if item.quantity <= 0:
                err_meta = lookup_pral_error("0204")
                msg = f"Line {idx}: Quantity must be greater than zero"
                errors.append(f"[0204] {msg}")
                line_item_errors.append({"item_seq": idx, "field": "quantity", "error_code": "0204", "message": msg})
                if err_meta:
                    structured_errors.append(err_meta.to_dict())

            if item.unit_price < 0:
                msg = f"Line {idx}: Unit price cannot be negative"
                errors.append(msg)
                line_item_errors.append({"item_seq": idx, "field": "unit_price", "error_code": "0301", "message": msg})

        serialized = None
        try:
            serialized = cls.serialize_draft_to_fbr_v112(db, tenant_id, data)
        except Exception:
            serialized = None

        is_valid = len(errors) == 0
        return InvoiceValidationResult(
            invoice_id=None,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            line_item_errors=line_item_errors,
            structured_errors=structured_errors,
            pral_status="Valid" if is_valid else "Invalid",
            fbr_ready=is_valid,
            official_live_verified=False,
            serialized_fbr_payload=serialized,
        )
