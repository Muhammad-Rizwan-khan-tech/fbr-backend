import random
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any
from backend.app.adapters.base import FBRAdapter, FBRAdapterResponse


class MockFBRAdapter(FBRAdapter):
    """
    Demo / Mock FBR Digital Invoicing Adapter.
    Simulates official FBR Digital Invoicing API behavior for local development,
    automated testing, and demo environments without hitting live tax servers.
    """

    def __init__(self, forced_scenario: str = "AUTO"):
        self.forced_scenario = forced_scenario # "AUTO", "VALID", "VALIDATION_ERROR", "REJECTION", "TIMEOUT", "PENDING"

    def _generate_fbr_invoice_number(self, invoice_number: str) -> str:
        timestamp_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = f"{random.randint(100000, 999999)}"
        return f"FBR-{timestamp_part}-{rand_suffix}"

    def _generate_qr_payload(
        self,
        fbr_inv_num: str,
        seller_ntn: str,
        buyer_ntn: str,
        total_tax: float,
        grand_total: float,
        date_str: str
    ) -> str:
        # FBR Digital Invoicing QR standard payload format
        raw_sig = f"{fbr_inv_num}|{seller_ntn}|{buyer_ntn}|{grand_total}|{total_tax}|{date_str}"
        sig_hash = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:16].upper()
        
        qr_content = (
            f"FBR-DI|INV:{fbr_inv_num}|S-NTN:{seller_ntn}|B-NTN:{buyer_ntn or 'N/A'}|"
            f"TOT:{grand_total:.2f}|TAX:{total_tax:.2f}|DT:{date_str}|SIG:{sig_hash}"
        )
        return qr_content

    def validate_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        warnings = []

        # Validate Seller requirements
        seller_ntn = invoice_data.get("seller_ntn", "").strip()
        if not seller_ntn:
            errors.append("Seller NTN is required for FBR submission")
        
        # Validate Items
        items = invoice_data.get("items", [])
        inv_type = (invoice_data.get("invoice_type") or "").upper()
        if not items and "NOTE" not in inv_type:
            errors.append("Invoice must contain at least one line item")
        
        for idx, item in enumerate(items, 1):
            hs_code = item.get("hs_code", "").strip()
            if not hs_code:
                errors.append(f"Line {idx}: HS Code is mandatory for FBR compliance")
            
            qty = float(item.get("quantity", 0))
            if qty <= 0:
                errors.append(f"Line {idx}: Quantity must be positive")
            
            rate = float(item.get("tax_rate", 0))
            if rate < 0:
                errors.append(f"Line {idx}: Tax rate cannot be negative")

        # Check special test triggers in notes or reference
        ref = invoice_data.get("reference_number", "") or ""
        notes = invoice_data.get("notes", "") or ""
        trigger_text = f"{ref} {notes}".upper()

        if "SIMULATE_VALIDATION_ERROR" in trigger_text or self.forced_scenario == "VALIDATION_ERROR":
            errors.append("FBR-VAL-104: Invalid Buyer NTN/STRN combination or unregistered province entity")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fbr_ready": len(errors) == 0
        }

    def submit_invoice(self, invoice_data: Dict[str, Any]) -> FBRAdapterResponse:
        # Pre-validate
        val_res = self.validate_invoice(invoice_data)
        if not val_res["is_valid"]:
            return FBRAdapterResponse(
                success=False,
                status="INVALID",
                error_code="FBR-VAL-100",
                error_message="; ".join(val_res["errors"]),
                is_retryable=False,
                raw_response={"validation_errors": val_res["errors"]}
            )

        ref = (invoice_data.get("reference_number") or "").upper()
        notes = (invoice_data.get("notes") or "").upper()
        scenario = self.forced_scenario

        if "ERR-TIMEOUT" in ref or "SIMULATE_TIMEOUT" in notes:
            scenario = "TIMEOUT"
        elif "ERR-REJ" in ref or "SIMULATE_REJECTION" in notes:
            scenario = "REJECTION"
        elif "ERR-PENDING" in ref or "SIMULATE_PENDING" in notes:
            scenario = "PENDING"
        elif "ERR-VAL" in ref:
            scenario = "VALIDATION_ERROR"

        # Scenario 1: TIMEOUT (Transient network error, retryable)
        if scenario == "TIMEOUT":
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_code="NET-504",
                error_message="Connection to FBR Digital Invoicing Gateway timed out after 10000ms. Service temporarily unavailable.",
                is_retryable=True,
                raw_response={"http_status": 504, "gateway_status": "TIMEOUT"}
            )

        # Scenario 2: REJECTION (Business rule rejection by tax authority)
        if scenario == "REJECTION":
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_code="FBR-REJ-204",
                error_message="Duplicate submission detected or Seller Sales Tax Registration (STRN) is inactive.",
                is_retryable=False,
                raw_response={"code": 204, "message": "Duplicate invoice reference detected in FBR tax ledger"}
            )

        # Scenario 3: PENDING (Asynchronous verification queue)
        if scenario == "PENDING":
            ref_id = f"REF-PRAL-{random.randint(1000000, 9999999)}"
            return FBRAdapterResponse(
                success=True,
                status="PENDING",
                fbr_reference=ref_id,
                error_code="FBR-QUEUED-202",
                error_message="Invoice queued for PRAL fiscal verification.",
                is_retryable=False,
                raw_response={"status": "QUEUED", "batch_reference": ref_id}
            )

        # Scenario 4: VALID (Default Success Scenario)
        inv_num = invoice_data.get("invoice_number", "INV-001")
        seller_ntn = invoice_data.get("seller_ntn", "1234567-8")
        buyer_ntn = invoice_data.get("buyer_ntn", "9876543-2")
        total_tax = float(invoice_data.get("total_tax", 0.0))
        grand_total = float(invoice_data.get("grand_total", 0.0))
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        fbr_inv_num = self._generate_fbr_invoice_number(inv_num)
        qr_payload = self._generate_qr_payload(
            fbr_inv_num, seller_ntn, buyer_ntn, total_tax, grand_total, date_str
        )
        fiscal_reference = f"PRAL-DI-{random.randint(10000000, 99999999)}"

        return FBRAdapterResponse(
            success=True,
            status="VALID",
            fbr_invoice_number=fbr_inv_num,
            fbr_reference=fiscal_reference,
            qr_code_data=qr_payload,
            error_code=None,
            error_message="Invoice verified and digitally registered with FBR central ledger",
            is_retryable=False,
            raw_response={
                "response_code": "00",
                "fbr_invoice_number": fbr_inv_num,
                "fiscal_reference": fiscal_reference,
                "status": "VALID",
                "registered_at": date_str,
                "tax_authority": "Federal Board of Revenue (Pakistan)",
                "system_mode": "DEMO_MOCK"
            }
        )

    def get_reference_data(self) -> Dict[str, Any]:
        return {
            "source": "FBR Digital Invoicing Mock System",
            "version": "2026.1",
            "rates": [18.00, 15.00, 1.00, 0.00],
            "uoms": ["NOS", "KGS", "LTR", "MTR", "BAG", "BOX"]
        }

    def parse_response(self, raw_response: Dict[str, Any]) -> FBRAdapterResponse:
        status = raw_response.get("status", "VALID")
        return FBRAdapterResponse(
            success=status == "VALID",
            status=status,
            fbr_invoice_number=raw_response.get("fbr_invoice_number"),
            fbr_reference=raw_response.get("fiscal_reference"),
            error_code=raw_response.get("error_code"),
            error_message=raw_response.get("message"),
            raw_response=raw_response
        )

    def get_status(self, submission_id: str) -> FBRAdapterResponse:
        return FBRAdapterResponse(
            success=True,
            status="VALID",
            error_message="Submission is confirmed valid in FBR system"
        )
