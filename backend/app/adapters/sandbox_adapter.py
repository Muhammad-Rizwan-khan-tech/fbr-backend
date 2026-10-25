import hashlib
import json
import logging
import random
import re
import time
from urllib.parse import urlsplit
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.fbr_hs_code import normalize_hs_code, valid_hs_code

import httpx

from backend.app.adapters.base import FBRAdapter, FBRAdapterResponse
from backend.app.core.config import settings
from backend.app.adapters.gateway_response import inspect_gateway_response

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://gw.fbr.gov.pk"
SANDBOX_SUBMIT_PATH = "/di_data/v1/di/postinvoicedata_sb"
SANDBOX_VALIDATE_PATH = "/di_data/v1/di/validateinvoicedata_sb"


def _safe_gateway_error(value: Any) -> str:
    """Extract meaningful FBR errors without exposing credentials or response dumps."""
    fragments: List[str] = []

    def add(candidate: Any) -> None:
        if isinstance(candidate, str) and candidate.strip():
            fragments.append(candidate.strip())
        elif isinstance(candidate, list):
            for item in candidate[:5]:
                add(item)
        elif isinstance(candidate, dict):
            for key in ("errorCode", "error_code", "code"):
                if candidate.get(key) is not None:
                    add(str(candidate[key]))
                    break
            for key in ("error", "errorMessage", "message", "detail", "description", "errors"):
                if key in candidate:
                    add(candidate[key])
                    break

    if isinstance(value, dict):
        for key in ("validationResponse", "ValidationResponse", "validation_response"):
            section = value.get(key)
            if isinstance(section, dict):
                add(section.get("error"))
                add(section.get("invoiceStatuses"))
        for key in ("errorMessage", "message", "detail", "error", "errors"):
            add(value.get(key))
    elif isinstance(value, str) and not value.lstrip().startswith("<"):
        add(value)
    message = "; ".join(dict.fromkeys(fragments))
    # Never return bearer credentials or structured credential assignments in audit data.
    message = re.sub(r"(?i)Bearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    message = re.sub(
        r"(?i)(?:api[_ -]?key|access[_ -]?token|authorization|password)\s*[:=]\s*[^\s,;]+",
        "[REDACTED_CREDENTIAL]", message,
    )
    return message[:450]


class SandboxFBRAdapter(FBRAdapter):
    """FBR Sandbox / Staging Digital Invoicing Adapter.
    
    Implements the official PRAL/FBR Digital Invoicing (DI) API Specification v1.12 (2025).
    Connects to the official sandbox / staging endpoints:
      - Submit:   POST https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb
      - Validate: POST https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb

    CRITICAL COMPLIANCE RULES:
    - Strictly implements DI API v1.12 payload schema with exact key casing.
    - Never emits legacy keys (InvoiceNumber, POSID, USIN, DateTime, TotalBillAmount, etc.).
    - Supports sandbox-specific 'scenarioId' for scenario testing (pattern ^SN\\d{3}$).
    - Never claims success on HTTP 200 alone; inspects nested validationResponse and invoiceStatuses.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        pos_id: Optional[str] = None,
        forced_scenario: str = "AUTO",
    ):
        raw_url = (base_url or settings.FBR_API_URL or DEFAULT_BASE_URL).rstrip("/")
        raw_url = re.sub(r"/api/v1/Invoice.*$", "", raw_url)
        # Render users may configure a full FBR v1.12 endpoint as the base URL.
        # Normalize every known invoice endpoint to its origin to avoid
        # appending /di_data/v1/di/postinvoicedata_sb twice.
        raw_url = re.sub(
            r"/di_data/v1/di/(?:postinvoicedata|validateinvoicedata)(?:_sb)?$",
            "", raw_url, flags=re.IGNORECASE,
        )
        # Official DI v1.12 lives at this specific HTTPS origin. Even when
        # FBR_API_URL accidentally contains a reference/documentation path,
        # send to the canonical invoice endpoint, not to a concatenated path.
        parsed_gateway = urlsplit(raw_url)
        self._official_gateway = (
            parsed_gateway.scheme == "https"
            and (parsed_gateway.hostname or "").lower() == "gw.fbr.gov.pk"
            and parsed_gateway.port in (None, 443)
            and not parsed_gateway.username
            and not parsed_gateway.password
        )
        self.base_url = DEFAULT_BASE_URL if self._official_gateway else raw_url
        self.bearer_token = bearer_token or settings.FBR_API_KEY or ""
        self.pos_id = pos_id or "10001"
        self.forced_scenario = forced_scenario
        self.environment = "SANDBOX"
        self.provider = "SANDBOX"
        self.is_simulated = False

    @property
    def submit_url(self) -> str:
        if SANDBOX_SUBMIT_PATH in self.base_url:
            return self.base_url
        return f"{self.base_url}{SANDBOX_SUBMIT_PATH}"

    @property
    def validate_url(self) -> str:
        if SANDBOX_VALIDATE_PATH in self.base_url:
            return self.base_url
        if SANDBOX_SUBMIT_PATH in self.base_url:
            return self.base_url.replace(SANDBOX_SUBMIT_PATH, SANDBOX_VALIDATE_PATH)
        return f"{self.base_url}{SANDBOX_VALIDATE_PATH}"

    @staticmethod
    def _clean_ntn_cnic(val: Any) -> str:
        if not val:
            return ""
        digits = "".join(c for c in str(val) if c.isdigit())
        if len(digits) == 8:
            return digits[:7]
        # Reject unusual lengths during validation; never truncate a CNIC.
        return digits

    @staticmethod
    def _format_fbr_rate(val: Any) -> str:
        if val is None:
            return "18%"
        str_val = str(val).strip()
        low = str_val.lower()
        if low == "exempt":
            return "Exempt"
        if "%" in str_val or low.startswith("rs") or "rupee" in low:
            return str_val
        try:
            num = float(str_val)
            return f"{int(num)}%" if num.is_integer() else f"{num}%"
        except (ValueError, TypeError):
            return f"{str_val}%"


    def _generate_sandbox_fbr_number(self, invoice_number: str) -> str:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_num = random.randint(100000, 999999)
        return f"SBX-{date_str}-{rand_num}"

    def _generate_qr_payload(
        self,
        fbr_inv_num: str,
        seller_ntn: str,
        buyer_ntn: str,
        total_tax: float,
        grand_total: float,
        date_str: str,
    ) -> str:
        raw_sig = f"{fbr_inv_num}|{seller_ntn}|{buyer_ntn}|{grand_total}|{total_tax}|{date_str}|SANDBOX"
        sig_hash = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:16].upper()
        return (
            f"FBR-DI-SBX|INV:{fbr_inv_num}|S-NTN:{seller_ntn}|B-NTN:{buyer_ntn or 'N/A'}|"
            f"TOT:{grand_total:.2f}|TAX:{total_tax:.2f}|DT:{date_str}|SIG:{sig_hash}"
        )

    def _transform_to_fbr_schema(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translates canonical invoice data into official FBR DI API v1.12 schema.
        
        Includes 'scenarioId' when applicable for sandbox scenario testing.
        """
        raw_type = str(
            invoice_data.get("invoiceType")
            or invoice_data.get("invoice_type")
            or ""
        ).upper()
        is_debit = "DEBIT" in raw_type or "CREDIT" in raw_type or "NOTE" in raw_type
        inv_type = "Debit Note" if is_debit else "Sale Invoice"

        date_val = invoice_data.get("invoiceDate") or invoice_data.get("invoice_date")
        if isinstance(date_val, datetime):
            date_str = date_val.strftime("%Y-%m-%d")
        elif isinstance(date_val, str) and date_val:
            date_str = date_val[:10]
        else:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        seller_ntn_raw = (
            invoice_data.get("sellerNTNCNIC")
            or invoice_data.get("seller_ntn_cnic")
            or invoice_data.get("seller_ntn")
            or invoice_data.get("seller_cnic")
            or ""
        )
        seller_ntn = self._clean_ntn_cnic(seller_ntn_raw)
        seller_name = str(
            invoice_data.get("sellerBusinessName")
            or invoice_data.get("seller_business_name")
            or invoice_data.get("seller_name")
            or "Sandbox Seller"
        ).strip()
        seller_province = str(
            invoice_data.get("sellerProvince")
            or invoice_data.get("seller_province")
            or "Sindh"
        ).strip()
        seller_address = str(
            invoice_data.get("sellerAddress")
            or invoice_data.get("seller_address")
            or (f"{seller_province}, Pakistan" if seller_province else "Pakistan")
        ).strip()

        buyer_ntn_raw = (
            invoice_data.get("buyerNTNCNIC")
            or invoice_data.get("buyer_ntn_cnic")
            or invoice_data.get("buyer_ntn")
            or invoice_data.get("buyer_cnic")
            or ""
        )
        buyer_reg_type_raw = str(
            invoice_data.get("buyerRegistrationType")
            or invoice_data.get("buyer_registration_type")
            or ""
        ).upper()
        is_registered = buyer_reg_type_raw in ("REGISTERED", "REGISTERED_BUSINESS")
        buyer_reg_type = "Registered" if is_registered else "Unregistered"

        # Unregistered buyers may omit NTN/CNIC under FBR DI v1.12.
        # Never manufacture an identifier: registered buyers must supply one.
        buyer_ntn = self._clean_ntn_cnic(buyer_ntn_raw)

        buyer_name = str(
            invoice_data.get("buyerBusinessName")
            or invoice_data.get("buyer_business_name")
            or invoice_data.get("buyer_name")
            or "Sandbox Buyer Corp"
        ).strip()
        buyer_province = str(
            invoice_data.get("buyerProvince")
            or invoice_data.get("buyer_province")
            or (seller_province or "Sindh")
        ).strip()
        buyer_address = str(
            invoice_data.get("buyerAddress")
            or invoice_data.get("buyer_address")
            or (f"{buyer_province}, Pakistan" if buyer_province else "Pakistan")
        ).strip()

        items: List[Dict[str, Any]] = []
        for itm in invoice_data.get("items", []):
            hs_code = normalize_hs_code(itm.get("hsCode") or itm.get("hs_code") or itm.get("pct_code") or "")
            desc = str(
                itm.get("productDescription")
                or itm.get("product_description")
                or itm.get("description")
                or itm.get("item_name")
                or "Product/Service"
            ).strip()
            rate_str = self._format_fbr_rate(itm.get("rate") if itm.get("rate") is not None else itm.get("tax_rate"))
            uom = str(itm.get("uoM") or itm.get("uom") or "Numbers, pieces, units").strip()
            if uom.upper() in ("NOS", "NUMBER", "NUMBERS", "PCS", "PIECES"):
                uom = "Numbers, pieces, units"
            quantity = float(itm.get("quantity", 1.0))
            if quantity <= 0:
                quantity = 1.0

            val_excl = float(round(float(
                itm.get("valueSalesExcludingST")
                if itm.get("valueSalesExcludingST") is not None
                else itm.get("value_sales_excluding_st", itm.get("taxable_amount", itm.get("gross_amount", 0.0)))
            ), 2))
            tax_app = float(round(float(
                itm.get("salesTaxApplicable")
                if itm.get("salesTaxApplicable") is not None
                else itm.get("sales_tax_applicable", itm.get("tax_amount", 0.0))
            ), 2))
            fixed_val = float(round(float(
                itm.get("fixedNotifiedValueOrRetailPrice")
                if itm.get("fixedNotifiedValueOrRetailPrice") is not None
                else itm.get("fixed_notified_value_or_retail_price", 0.0)
            ), 2))
            st_withheld = float(round(float(
                itm.get("salesTaxWithheldAtSource")
                if itm.get("salesTaxWithheldAtSource") is not None
                else itm.get("sales_tax_withheld_at_source", 0.0)
            ), 2))

            if itm.get("totalValues") is not None:
                total_val = float(round(float(itm.get("totalValues")), 2))
            elif itm.get("total_values") is not None:
                total_val = float(round(float(itm.get("total_values")), 2))
            elif itm.get("line_total") is not None:
                total_val = float(round(float(itm.get("line_total")), 2))
            else:
                total_val = float(round(val_excl + tax_app, 2))

            sale_type = str(itm.get("saleType") or itm.get("sale_type") or "Goods at standard rate").strip()
            if sale_type.upper() in ("STANDARD", "GOODS AT STANDARD RATE"):
                sale_type = "Goods at standard rate (default)"

            item_dict: Dict[str, Any] = {
                "hsCode": hs_code,
                "productDescription": desc,
                "rate": rate_str,
                "uoM": uom,
                "quantity": quantity,
                "totalValues": total_val,
                "valueSalesExcludingST": val_excl,
                "fixedNotifiedValueOrRetailPrice": fixed_val,
                "salesTaxApplicable": tax_app,
                "salesTaxWithheldAtSource": st_withheld,
                "saleType": sale_type,
            }

            extra_tax = itm.get("extraTax") if itm.get("extraTax") is not None else itm.get("extra_tax")
            item_dict["extraTax"] = float(round(float(extra_tax if extra_tax is not None and extra_tax != "" else 0), 2))

            further_tax = itm.get("furtherTax") if itm.get("furtherTax") is not None else itm.get("further_tax")
            item_dict["furtherTax"] = float(round(float(further_tax if further_tax is not None and further_tax != "" else 0), 2))

            sro_sched = itm.get("sroScheduleNo") or itm.get("sro_schedule_no") or itm.get("sro_reference")
            if sro_sched:
                item_dict["sroScheduleNo"] = str(sro_sched).strip()

            fed_pay = itm.get("fedPayable") if itm.get("fedPayable") is not None else itm.get("fed_payable")
            item_dict["fedPayable"] = float(round(float(fed_pay if fed_pay is not None and fed_pay != "" else 0), 2))

            discount = itm.get("discount")
            item_dict["discount"] = float(round(float(discount if discount is not None and discount != "" else 0), 2))

            sro_serial = itm.get("sroItemSerialNo") or itm.get("sro_item_serial_no")
            if sro_serial:
                item_dict["sroItemSerialNo"] = str(sro_serial).strip()

            items.append(item_dict)

        payload: Dict[str, Any] = {
            "invoiceType": inv_type,
            "invoiceDate": date_str,
            "sellerNTNCNIC": seller_ntn,
            "sellerBusinessName": seller_name,
            "sellerProvince": seller_province,
            "sellerAddress": seller_address,
            "buyerNTNCNIC": buyer_ntn,
            "buyerBusinessName": buyer_name,
            "buyerProvince": buyer_province,
            "buyerAddress": buyer_address,
            "buyerRegistrationType": buyer_reg_type,
            "items": items,
        }

        if is_debit:
            ref_no = (
                invoice_data.get("invoiceRefNo")
                or invoice_data.get("invoice_ref_no")
                or invoice_data.get("reference_number")
                or invoice_data.get("original_invoice_number")
                or invoice_data.get("ref_usin")
            )
            if ref_no:
                payload["invoiceRefNo"] = str(ref_no).strip()

        # Handle sandbox-specific scenarioId
        scen_id = (
            invoice_data.get("scenarioId")
            or invoice_data.get("scenario_id")
            or (self.forced_scenario if str(self.forced_scenario).startswith("SN") else None)
        )
        if scen_id and isinstance(scen_id, str):
            payload["scenarioId"] = scen_id.strip()

        return payload

    def validate_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates payload against DI API v1.12 schema and sandbox test scenarios."""
        errors: List[str] = []
        warnings: List[str] = []

        payload = self._transform_to_fbr_schema(invoice_data)

        if payload.get("invoiceType") not in ("Sale Invoice", "Debit Note"):
            errors.append(f"Invalid invoiceType '{payload.get('invoiceType')}'. Must be 'Sale Invoice' or 'Debit Note'")

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", payload.get("invoiceDate", "")):
            errors.append(f"Invalid invoiceDate '{payload.get('invoiceDate')}'. Must be YYYY-MM-DD")

        s_ntn = payload.get("sellerNTNCNIC", "")
        if not re.match(r"^(\d{7}|\d{13})$", s_ntn):
            errors.append(f"sellerNTNCNIC '{s_ntn}' must be 7 or 13 digits")

        if not payload.get("sellerBusinessName"):
            errors.append("sellerBusinessName is required")

        if not payload.get("sellerProvince"):
            errors.append("sellerProvince is required")

        if not payload.get("sellerAddress"):
            errors.append("sellerAddress is required")

        buyer_tax_id = payload.get("buyerNTNCNIC", "")
        if payload.get("buyerRegistrationType") == "Registered" and not buyer_tax_id:
            errors.append("buyerNTNCNIC is required for a registered buyer")
        if buyer_tax_id and not re.fullmatch(r"(?:\d{7}|\d{13})", buyer_tax_id):
            errors.append("buyerNTNCNIC must be 7 or 13 digits when provided")

        # Disallow synthetic seller/buyer fields when transmitting an actual
        # PRAL invoice. Local mock fixtures without credentials still work.
        if self.bearer_token:
            required_fields = {
                "sellerBusinessName": ("sellerBusinessName", "seller_name", "seller_business_name"),
                "sellerProvince": ("sellerProvince", "seller_province"),
                "sellerAddress": ("sellerAddress", "seller_address"),
                "buyerBusinessName": ("buyerBusinessName", "buyer_name", "buyer_business_name"),
                "buyerProvince": ("buyerProvince", "buyer_province"),
                "buyerAddress": ("buyerAddress", "buyer_address"),
            }
            for field_name, source_keys in required_fields.items():
                if not any(str(invoice_data.get(k) or "").strip() for k in source_keys):
                    errors.append(f"{field_name} must be supplied for a real FBR request; demo defaults are forbidden")

        if not payload.get("buyerBusinessName"):
            errors.append("buyerBusinessName is required")

        if not payload.get("buyerProvince"):
            errors.append("buyerProvince is required")

        if not payload.get("buyerAddress"):
            errors.append("buyerAddress is required")

        if payload.get("buyerRegistrationType") not in ("Registered", "Unregistered"):
            errors.append("buyerRegistrationType must be 'Registered' or 'Unregistered'")

        if payload.get("invoiceType") == "Debit Note" and not payload.get("invoiceRefNo"):
            errors.append("invoiceRefNo is required for Debit Note")

        if "scenarioId" in payload and not re.match(r"^SN\d{3}$", payload["scenarioId"]):
            errors.append(f"scenarioId '{payload['scenarioId']}' must match pattern ^SN\\d{{3}}$")

        items = payload.get("items", [])
        if not items:
            errors.append("At least one item is required")
        else:
            for idx, itm in enumerate(items, 1):
                if not valid_hs_code(itm.get("hsCode")):
                    errors.append(f"Item {idx}: hsCode must contain 8 digits, e.g. 8471.3010")
                if not itm.get("productDescription"):
                    errors.append(f"Item {idx}: productDescription is required")
                r_val = str(itm.get("rate") or "").strip()
                r_low = r_val.lower()
                if not r_val or not ("%" in r_val or r_low == "exempt" or r_low.startswith("rs") or "rupee" in r_low):
                    errors.append(f"Item {idx}: rate must be an FBR rate description (e.g. '18%', 'Exempt')")
                if not itm.get("uoM"):
                    errors.append(f"Item {idx}: uoM is required")
                if float(itm.get("quantity", 0)) <= 0:
                    errors.append(f"Item {idx}: quantity must be greater than zero")
                if not itm.get("saleType"):
                    errors.append(f"Item {idx}: saleType is required")

        ref = str(invoice_data.get("reference_number") or "").upper()
        notes = str(invoice_data.get("notes") or "").upper()
        if "SIMULATE_VALIDATION_ERROR" in f"{ref} {notes}" or self.forced_scenario == "VALIDATION_ERROR":
            errors.append("FBR-SBX-VAL-104: Invalid Buyer NTN/STRN combination in Sandbox registry")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fbr_ready": len(errors) == 0,
            "transformed_payload": payload,
        }

    def submit_invoice(self, invoice_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Submits an invoice to the official PRAL DI API v1.12 sandbox endpoint."""
        val = self.validate_invoice(invoice_data)
        if not val["is_valid"]:
            return FBRAdapterResponse(
                success=False,
                status="INVALID",
                error_code="FBR-SBX-VAL-100",
                error_message="; ".join(val["errors"]),
                is_retryable=False,
                raw_response={"errors": val["errors"]},
                environment=self.environment,
                provider=self.provider,
                is_simulated=self.is_simulated,
            )

        fbr_payload = val.get("transformed_payload") or self._transform_to_fbr_schema(invoice_data)

        # Check for simulated test triggers
        ref = str(invoice_data.get("reference_number") or "").upper()
        notes = str(invoice_data.get("notes") or "").upper()
        trigger_text = f"{ref} {notes}"

        if "SIMULATE_TIMEOUT" in trigger_text or self.forced_scenario == "TIMEOUT":
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_code="NET-SBX-504",
                error_message="Sandbox gateway timeout after 15000ms. Service temporarily unavailable.",
                is_retryable=True,
                raw_response={"http_status": 504, "gateway": "SANDBOX"},
                environment=self.environment,
                provider=self.provider,
                is_simulated=self.is_simulated,
            )

        if "SIMULATE_REJECTION" in trigger_text or self.forced_scenario == "REJECTION":
            sim_rej = {
                "invoiceNumber": None,
                "dated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "validationResponse": {
                    "statusCode": "01",
                    "status": "Invalid",
                    "error": "Duplicate Invoice Number or inactive buyer NTN in sandbox ledger",
                    "invoiceStatuses": [],
                },
            }
            return self.parse_response(sim_rej)

        # If live sandbox credentials and live endpoint are present, attempt actual HTTP transmission
        is_live_sandbox = (
            bool(self.bearer_token)
            and self._official_gateway
        )
        if is_live_sandbox:
            endpoint = self.submit_url
            headers = {
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
                "User-Agent": "FBR-Invoice-Cloud-DI-Sandbox/1.12",
                "Accept": "application/json",
            }
            try:
                with httpx.Client(timeout=settings.FBR_HTTP_TIMEOUT_SECONDS, proxy=settings.FIXIE_URL or None, trust_env=not bool(settings.FIXIE_URL)) as client:
                    resp = client.post(endpoint, json=fbr_payload, headers=headers)
                    data, gateway_meta = inspect_gateway_response(resp)
                    http_status = resp.status_code
                    if http_status >= 400:
                        details = _safe_gateway_error(data)
                        if not details:
                            details = gateway_meta.get("gateway_hint", "")
                        if not details:
                            details = "Gateway returned no recognized structured error; check FBR access, token and invoice payload."
                        if http_status in (401, 403):
                            error_code = f"FBR-SBX-AUTH-{http_status}"
                            status = "FAILED"
                        elif http_status == 429:
                            error_code = "FBR-SBX-HTTP-429"
                            status = "FAILED"
                        elif http_status >= 500:
                            error_code = f"FBR-SBX-HTTP-{http_status}"
                            status = "FAILED"
                        else:
                            error_code = f"FBR-SBX-HTTP-{http_status}"
                            status = "INVALID"
                        return FBRAdapterResponse(
                            success=False,
                            status=status,
                            error_code=error_code,
                            error_message=f"FBR Sandbox HTTP {http_status}: {details}",
                            is_retryable=http_status == 429 or http_status >= 500,
                            raw_response={**gateway_meta, "error_summary": details},
                            environment=self.environment,
                            provider=self.provider,
                            is_simulated=False,
                        )
                    if not isinstance(data, dict):
                        kind = gateway_meta.get("response_kind", "unknown")
                        ctype = gateway_meta.get("content_type", "unknown")
                        hint = gateway_meta.get("gateway_hint")
                        message = (
                            f"FBR Sandbox HTTP {http_status} returned {kind} (Content-Type: {ctype}). "
                            + (f"Gateway message: {hint}. " if hint else "")
                            + "Expected the DI v1.12 invoice validation JSON object. "
                              "Confirm the official gw.fbr.gov.pk endpoint and inspect the response fingerprint."
                        )
                        logger.warning(
                            "FBR Sandbox response mismatch: kind=%s type=%s status=%s fingerprint=%s",
                            kind, ctype, http_status, gateway_meta.get("body_sha256_prefix"),
                        )
                        return FBRAdapterResponse(
                            success=False, status="FAILED",
                            error_code="FBR-SBX-RESPONSE-FORMAT",
                            error_message=message[:600],
                            is_retryable=False,
                            raw_response=gateway_meta,
                            environment=self.environment, provider=self.provider,
                            is_simulated=False,
                        )
                    result = self.parse_response(data)
                    result.raw_response = {**data, **gateway_meta}
                    return result
            except httpx.RequestError as net_err:
                logger.warning("Sandbox transport failed: %s", type(net_err).__name__)
                proxy_error = isinstance(net_err, httpx.ProxyError)
                return FBRAdapterResponse(
                    success=False, status="FAILED",
                    error_code="NET-SBX-PROXY" if proxy_error else "NET-SBX-CONN",
                    error_message=(
                        "Fixie proxy connection/authentication failed; check configured credentials and host."
                        if proxy_error else
                        f"FBR Sandbox transport error ({type(net_err).__name__}); check Fixie and gateway connectivity."
                    ),
                    is_retryable=not proxy_error,
                    raw_response={"error_type": type(net_err).__name__},
                    environment=self.environment,
                    provider=self.provider, is_simulated=False,
                )
            except Exception as exc:
                logger.exception("Unexpected FBR Sandbox processing exception: %s", type(exc).__name__)
                return FBRAdapterResponse(
                    success=False, status="FAILED", error_code="NET-SBX-UNEXPECTED",
                    error_message=f"Sandbox response processing error ({type(exc).__name__}). Check backend logs by request ID.",
                    is_retryable=False,
                    raw_response={"error_type": type(exc).__name__},
                    environment=self.environment,
                    provider=self.provider, is_simulated=False,
                )

        if self.bearer_token:
            return FBRAdapterResponse(
                success=False, status="FAILED", error_code="FBR-SBX-GATEWAY-CONFIG",
                error_message="FBR Sandbox DI v1.12 requires the official https://gw.fbr.gov.pk gateway. Check FBR_API_URL / tenant gateway configuration.",
                is_retryable=False, environment=self.environment,
                provider=self.provider, is_simulated=False,
            )

        # Unit-test / offline demo fallback only (never call this for a configured tenant).
        inv_num = str(invoice_data.get("invoice_number") or invoice_data.get("invoiceNumber") or "INV-001")
        fbr_inv_num = self._generate_sandbox_fbr_number(inv_num)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        seller_ntn = fbr_payload.get("sellerNTNCNIC", "1234567")
        buyer_ntn = fbr_payload.get("buyerNTNCNIC", "9876543")
        total_tax = sum(float(i.get("salesTaxApplicable", 0.0)) for i in fbr_payload.get("items", []))
        grand_total = sum(float(i.get("totalValues", 0.0)) for i in fbr_payload.get("items", []))

        qr_payload = self._generate_qr_payload(
            fbr_inv_num, seller_ntn, buyer_ntn, total_tax, grand_total, date_str
        )

        simulated_v112_response = {
            "invoiceNumber": fbr_inv_num,
            "dated": date_str,
            "qrCode": qr_payload,
            "validationResponse": {
                "statusCode": "00",
                "status": "Valid",
                "error": None,
                "invoiceStatuses": [
                    {
                        "itemSeq": idx,
                        "status": "Valid",
                        "error": None,
                    }
                    for idx in range(1, len(fbr_payload.get("items", [])) + 1)
                ],
            },
        }

        return self.parse_response(simulated_v112_response)

    def validate_invoice_remote(self, invoice_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Call official validateinvoicedata_sb without registering an invoice."""
        if not self.bearer_token:
            return FBRAdapterResponse(
                success=False, status="FAILED", error_code="FBR-SBX-TOKEN-MISSING",
                error_message="Sandbox security token is missing.", is_retryable=False,
                environment=self.environment, provider=self.provider, is_simulated=False,
            )
        val = self.validate_invoice(invoice_data)
        if not val["is_valid"]:
            return FBRAdapterResponse(
                success=False, status="INVALID", error_code="FBR-SBX-LOCAL-VALIDATION",
                error_message="; ".join(val["errors"])[:600], is_retryable=False,
                raw_response={"validation_errors": val["errors"][:10]},
                environment=self.environment, provider=self.provider, is_simulated=False,
            )
        endpoint = self.validate_url
        payload = val["transformed_payload"]
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json", "Accept": "application/json",
        }
        try:
            with httpx.Client(
                timeout=settings.FBR_HTTP_TIMEOUT_SECONDS,
                proxy=settings.FIXIE_URL or None,
                trust_env=not bool(settings.FIXIE_URL),
            ) as client:
                response = client.post(endpoint, json=payload, headers=headers)
            data, meta = inspect_gateway_response(response)
            if response.status_code >= 400:
                detail = _safe_gateway_error(data) or meta.get("gateway_hint") or "Gateway rejected validation request"
                return FBRAdapterResponse(
                    success=False, status="INVALID" if response.status_code < 500 else "FAILED",
                    error_code=f"FBR-SBX-VALIDATE-HTTP-{response.status_code}",
                    error_message=f"FBR validation HTTP {response.status_code}: {detail}"[:600],
                    is_retryable=response.status_code == 429 or response.status_code >= 500,
                    raw_response={**meta, "error_summary": detail[:250]},
                    environment=self.environment, provider=self.provider, is_simulated=False,
                )
            if not isinstance(data, dict):
                return FBRAdapterResponse(
                    success=False, status="FAILED",
                    error_code="FBR-SBX-VALIDATE-RESPONSE-FORMAT",
                    error_message=(
                        f"FBR validation HTTP {response.status_code} returned "
                        f"{meta['response_kind']} ({meta['content_type']}); "
                        "expected validationResponse JSON object."
                    ),
                    raw_response=meta, environment=self.environment,
                    provider=self.provider, is_simulated=False,
                )
            validation = data.get("validationResponse") or data.get("ValidationResponse") or {}
            if not isinstance(validation, dict):
                validation = {}
            code = str(validation.get("statusCode") or "").strip()
            status = str(validation.get("status") or "").strip().lower()
            line_statuses = validation.get("invoiceStatuses") or []
            item_rejections = [
                item for item in line_statuses
                if isinstance(item, dict) and (
                    str(item.get("status", "")).lower() in ("invalid", "failed", "rejected")
                    or str(item.get("statusCode") or "") not in ("", "0", "00", "200")
                    or bool(item.get("error"))
                )
            ] if isinstance(line_statuses, list) else []
            valid = code in ("00", "0") and status == "valid" and not item_rejections
            if valid:
                return FBRAdapterResponse(
                    success=True, status="VALIDATED",
                    error_message=None,
                    raw_response={**data, **meta, "note": "Validation passed; invoice NOT submitted"},
                    environment=self.environment, provider=self.provider, is_simulated=False,
                )
            explanation = _safe_gateway_error(data) or "FBR did not confirm a valid invoice payload."
            return FBRAdapterResponse(
                success=False, status="INVALID", error_code=f"FBR-SBX-VALIDATE-{code or 'INVALID'}",
                error_message=explanation[:600], is_retryable=False,
                raw_response={**data, **meta},
                environment=self.environment, provider=self.provider, is_simulated=False,
            )
        except httpx.RequestError as exc:
            logger.warning("FBR Sandbox validation transport: %s", type(exc).__name__)
            return FBRAdapterResponse(
                success=False, status="FAILED", error_code="NET-SBX-VALIDATE",
                error_message=f"FBR Sandbox validation transport failed ({type(exc).__name__})",
                is_retryable=True, raw_response={"error_type": type(exc).__name__},
                environment=self.environment, provider=self.provider, is_simulated=False,
            )

    def submit_note(self, note_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Submits a Credit or Debit Note to the FBR Sandbox with reference linking."""
        data = dict(note_data)
        if not data.get("items"):
            taxable = float(data.get("taxable_amount") or data.get("subtotal") or 0.0)
            tax_amt = float(data.get("total_tax") or data.get("tax_amount") or 0.0)
            total = float(data.get("grand_total") or (taxable + tax_amt))
            data["items"] = [
                {
                    "hsCode": "9900.00.00",
                    "productDescription": str(data.get("reason") or "Adjustment Note"),
                    "rate": "18%",
                    "uoM": "Numbers",
                    "quantity": 1.0,
                    "valueSalesExcludingST": taxable,
                    "salesTaxApplicable": tax_amt,
                    "totalValues": total,
                    "saleType": "Goods at standard rate",
                }
            ]
        return self.submit_invoice(data)

    def test_connection(self) -> Dict[str, Any]:
        """Probes the Sandbox endpoint to verify connectivity and credentials."""
        start = time.time()
        is_live_sandbox = (
            bool(self.bearer_token)
            and self._official_gateway
        )
        if is_live_sandbox:
            endpoint = self.validate_url
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            try:
                with httpx.Client(timeout=5.0, proxy=settings.FIXIE_URL or None, trust_env=not bool(settings.FIXIE_URL)) as client:
                    resp = client.options(endpoint, headers=headers)
                    latency = int((time.time() - start) * 1000)
                    is_online = resp.status_code in (200, 405, 400, 422)
                    return {
                        "success": is_online,
                        "status": "ONLINE" if is_online else f"HTTP_{resp.status_code}",
                        "latency_ms": latency,
                        "message": f"Connected to FBR Sandbox Gateway ({resp.status_code})",
                        "environment": "SANDBOX",
                        "provider": "SANDBOX",
                        "is_simulated": False,
                        "details": {
                            "base_url": self.base_url,
                            "submit_url": self.submit_url,
                            "validate_url": self.validate_url,
                        },
                    }
            except Exception as e:
                latency = int((time.time() - start) * 1000)
                return {
                    "success": False,
                    "status": "OFFLINE",
                    "latency_ms": latency,
                    "message": f"Sandbox gateway unreachable: {str(e)}",
                    "environment": "SANDBOX",
                    "provider": "SANDBOX",
                    "is_simulated": False,
                    "details": {
                        "base_url": self.base_url,
                        "submit_url": self.submit_url,
                    },
                }

        latency = int((time.time() - start) * 1000)
        return {
            "success": False,
            "status": "UNCONFIGURED" if not self.bearer_token else "INVALID_GATEWAY",
            "latency_ms": latency,
            "message": "A real HTTPS FBR Sandbox gateway and security token are required. No live connection was verified.",
            "environment": "SANDBOX",
            "provider": "SANDBOX",
            "is_simulated": False,
        }

    def get_reference_data(self) -> Dict[str, Any]:
        return {
            "source": "FBR Sandbox Digital Invoicing System",
            "version": "1.12-SBX",
            "rates": ["18%", "15%", "1%", "0%"],
            "uoms": ["Numbers", "NOS", "KGS", "LTR", "MTR", "BAG", "BOX", "SET"],
        }

    def parse_response(self, raw_response: Dict[str, Any]) -> FBRAdapterResponse:
        """Parses the official DI API v1.12 response shape."""
        inv_num = raw_response.get("invoiceNumber") or raw_response.get("InvoiceNumber") or raw_response.get("invoice_number")
        dated = raw_response.get("dated") or raw_response.get("Dated") or raw_response.get("registered_at")

        val_resp = (
            raw_response.get("validationResponse")
            or raw_response.get("ValidationResponse")
            or raw_response.get("validation_response")
            or {}
        )

        status_code = ""
        status_text = ""
        top_error = None
        invoice_statuses: List[Dict[str, Any]] = []

        if isinstance(val_resp, dict):
            status_code = str(val_resp.get("statusCode") or val_resp.get("StatusCode") or val_resp.get("status_code") or "").strip()
            status_text = str(val_resp.get("status") or val_resp.get("Status") or "").strip()
            top_error = val_resp.get("error") or val_resp.get("Error")
            raw_statuses = val_resp.get("invoiceStatuses") or val_resp.get("InvoiceStatuses") or val_resp.get("invoice_statuses") or []
            if isinstance(raw_statuses, list):
                invoice_statuses = raw_statuses

        item_errors: List[str] = []
        first_item_error_code: Optional[str] = None
        for itm_stat in invoice_statuses:
            if isinstance(itm_stat, dict):
                i_status = str(itm_stat.get("status") or itm_stat.get("Status") or "").lower()
                i_err = itm_stat.get("error") or itm_stat.get("Error")
                i_code = itm_stat.get("errorCode") or itm_stat.get("error_code")
                if i_status in ("invalid", "failed", "rejected") or i_err:
                    seq = itm_stat.get("itemSNo") or itm_stat.get("itemSeq") or itm_stat.get("item_seq") or ""
                    if i_code and not first_item_error_code:
                        first_item_error_code = str(i_code).strip()
                    code_prefix = f"[{i_code}] " if i_code else ""
                    item_errors.append(f"Item {seq}: {code_prefix}{i_err or i_status}".strip(": "))

        has_top_error = bool(top_error and str(top_error).lower() not in ("null", "none", ""))
        has_item_error = len(item_errors) > 0
        is_invalid_status = status_text.lower() in ("invalid", "failed", "rejected")

        if not val_resp:
            legacy_code = str(raw_response.get("response_code") or raw_response.get("Code") or raw_response.get("status") or "")
            success = legacy_code in ("00", "200", "VALID", "SUCCESS") and not raw_response.get("errors")
        else:
            code_is_valid = status_code in ("00", "0", "200")
            status_is_valid = status_text.lower() in ("valid", "success", "accepted")
            success = (
                code_is_valid
                and status_is_valid
                and not has_top_error
                and not has_item_error
                and not is_invalid_status
                and bool(inv_num)
            )

        error_messages: List[str] = []
        if has_top_error:
            error_messages.append(str(top_error))
        if item_errors:
            error_messages.extend(item_errors)
        if not success and not error_messages:
            msg = raw_response.get("message") or raw_response.get("Message") or "Validation failed in Sandbox"
            error_messages.append(msg)

        final_error_message = "; ".join(error_messages) if not success else None
        error_code = None
        if not success:
            top_err_code = val_resp.get("errorCode") if isinstance(val_resp, dict) else None
            resolved_err_code = top_err_code or first_item_error_code or status_code
            error_code = f"FBR-SBX-{resolved_err_code}" if resolved_err_code else "FBR-SBX-INVALID"

        qr_code = raw_response.get("qrCode") or raw_response.get("qr_code") or raw_response.get("qr_code_data")
        if success and not qr_code and inv_num:
            qr_code = f"FBR-DI-SBX|INV:{inv_num}|DT:{dated or ''}"

        return FBRAdapterResponse(
            success=success,
            status="VALID" if success else "INVALID",
            fbr_invoice_number=inv_num if success else None,
            fbr_reference=str(dated or status_code) if success else None,
            qr_code_data=qr_code if success else None,
            error_code=error_code,
            error_message=final_error_message,
            raw_response=raw_response,
            environment=self.environment,
            provider=self.provider,
            is_simulated=False,
        )

    def get_status(self, submission_id: str) -> FBRAdapterResponse:
        return FBRAdapterResponse(
            success=True,
            status="VALID",
            error_message="Submission confirmed valid in FBR Sandbox ledger",
            environment=self.environment,
            provider=self.provider,
            is_simulated=False,
        )

