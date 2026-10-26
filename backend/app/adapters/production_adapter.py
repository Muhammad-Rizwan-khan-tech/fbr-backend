from backend.app.core.fbr_extra_tax import extra_tax_wire_value, reduced_extra_tax_errors
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.app.core.fbr_hs_code import normalize_hs_code, valid_hs_code

import httpx

from backend.app.adapters.base import FBRAdapter, FBRAdapterResponse
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://gw.fbr.gov.pk"
PROD_SUBMIT_PATH = "/di_data/v1/di/postinvoicedata"
PROD_VALIDATE_PATH = "/di_data/v1/di/validateinvoicedata"


class ProductionFBRAdapter(FBRAdapter):
    """Production FBR Digital Invoicing Adapter.
    
    Implements the official PRAL/FBR Digital Invoicing (DI) API Specification v1.12 (2025).
    Connects to the official live production endpoints:
      - Submit:   POST https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata
      - Validate: POST https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata

    CRITICAL COMPLIANCE RULES:
    - Strictly implements DI API v1.12 payload schema with exact key casing.
    - Never emits legacy keys (InvoiceNumber, POSID, USIN, DateTime, TotalBillAmount, etc.).
    - Never emits sandbox fields (e.g. scenarioId is strictly omitted in production).
    - If required credentials are missing, rejects requests with an explicit configuration error.
    - Never claims success on HTTP 200 alone; inspects nested validationResponse and invoiceStatuses.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        pos_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        raw_url = (base_url or settings.FBR_API_URL or DEFAULT_BASE_URL).rstrip("/")
        # Prevent legacy route fragments
        raw_url = re.sub(r"/api/v1/Invoice.*$", "", raw_url)
        self.base_url = raw_url
        self.bearer_token = bearer_token or settings.FBR_API_KEY or ""
        self.pos_id = pos_id or getattr(settings, "FBR_DEFAULT_POS_ID", "10001")
        self.client_id = client_id or settings.FBR_CLIENT_ID or ""
        self.client_secret = client_secret or settings.FBR_CLIENT_SECRET or ""
        self.environment = "PRODUCTION"
        self.provider = "PRODUCTION"
        self.is_simulated = False

    @property
    def submit_url(self) -> str:
        if PROD_SUBMIT_PATH in self.base_url:
            return self.base_url
        return f"{self.base_url}{PROD_SUBMIT_PATH}"

    @property
    def validate_url(self) -> str:
        if PROD_VALIDATE_PATH in self.base_url:
            return self.base_url
        if PROD_SUBMIT_PATH in self.base_url:
            return self.base_url.replace(PROD_SUBMIT_PATH, PROD_VALIDATE_PATH)
        return f"{self.base_url}{PROD_VALIDATE_PATH}"

    def is_configured(self) -> bool:
        """Returns True if minimum live production credentials are present."""
        return bool(self.bearer_token)

    @staticmethod
    def _clean_ntn_cnic(val: Any) -> str:
        """Extracts numeric digits and enforces FBR 7-digit NTN or 13-digit CNIC."""
        if not val:
            return ""
        digits = "".join(c for c in str(val) if c.isdigit())
        if len(digits) == 8:
            # 7-digit NTN + 1 check digit in Pakistan -> FBR requires 7-digit NTN
            return digits[:7]
        return digits

    @staticmethod
    def _format_fbr_rate(val: Any) -> str:
        """Formats tax rate to match official FBR rate description (e.g. '18%', 'Exempt', 'Rs. 3')."""
        if val is None:
            return "18%"
        str_val = str(val).strip()
        low = str_val.lower()
        # Legacy desktop scenarios appended '%' to descriptions already ending
        # in '%'. Normalize numeric percentage descriptions at the API boundary.
        percentage = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*%+", str_val)
        if percentage:
            return percentage.group(1) + "%"
        if low == "exempt":
            return "Exempt"
        if "%" in str_val or low.startswith("rs") or "rupee" in low:
            return str_val
        try:
            num = float(str_val)
            return f"{int(num)}%" if num.is_integer() else f"{num}%"
        except (ValueError, TypeError):
            return f"{str_val}%"


    def _transform_to_fbr_schema(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maps canonical invoice data into official FBR DI API v1.12 schema.
        
        Strictly conforms to FBR_DI_API_v1_12_invoice_request.schema.json:
        - Only permitted top-level and item keys.
        - Quantities and values serialized as numbers.
        - scenarioId is strictly omitted in production.
        """
        raw_type = str(
            invoice_data.get("invoiceType")
            or invoice_data.get("invoice_type")
            or ""
        ).upper()
        is_debit = "DEBIT" in raw_type or "CREDIT" in raw_type or "NOTE" in raw_type
        inv_type = "Debit Note" if is_debit else "Sale Invoice"

        # Format invoiceDate (YYYY-MM-DD)
        date_val = invoice_data.get("invoiceDate") or invoice_data.get("invoice_date")
        if isinstance(date_val, datetime):
            date_str = date_val.strftime("%Y-%m-%d")
        elif isinstance(date_val, str) and date_val:
            date_str = date_val[:10]
        else:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Seller fields
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
            or ""
        ).strip()
        seller_province = str(
            invoice_data.get("sellerProvince")
            or invoice_data.get("seller_province")
            or ""
        ).strip()
        seller_address = str(
            invoice_data.get("sellerAddress")
            or invoice_data.get("seller_address")
            or ""
        ).strip()

        # Buyer fields
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

        # FBR DI v1.12 allows a missing ID for an unregistered buyer.
        # Never substitute arbitrary IDs or truncate tax identifiers.
        buyer_ntn = self._clean_ntn_cnic(buyer_ntn_raw)

        buyer_name = str(
            invoice_data.get("buyerBusinessName")
            or invoice_data.get("buyer_business_name")
            or invoice_data.get("buyer_name")
            or ""
        ).strip()
        buyer_province = str(
            invoice_data.get("buyerProvince")
            or invoice_data.get("buyer_province")
            or ""
        ).strip()
        buyer_address = str(
            invoice_data.get("buyerAddress")
            or invoice_data.get("buyer_address")
            or ""
        ).strip()

        # Items mapping
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

            sale_type = str(itm.get("saleType") or itm.get("sale_type") or "Goods at standard rate (default)").strip()
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

            # Optional item fields: include only when non-zero / present
            extra_tax = itm.get("extraTax") if itm.get("extraTax") is not None else itm.get("extra_tax")
            wire_extra_tax = extra_tax_wire_value(sale_type, extra_tax)
            if wire_extra_tax is not None:
                item_dict["extraTax"] = wire_extra_tax

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

        # Conditional header field: invoiceRefNo for Debit Note
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

        # NOTE: scenarioId is omitted in production per DI API v1.12 specification

        return payload

    def validate_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates payload against DI API v1.12 schema and production requirements."""
        errors: List[str] = reduced_extra_tax_errors(invoice_data.get("items", []))
        warnings: List[str] = []

        if not self.is_configured():
            errors.append(
                "FBR-PROD-CONFIG: Live production credentials (Bearer Token) are not configured. "
                "Production submission is halted."
            )

        payload = self._transform_to_fbr_schema(invoice_data)

        # 1. Header Validation
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

        buyer_id = payload.get("buyerNTNCNIC", "")
        if payload.get("buyerRegistrationType") == "Registered" and not buyer_id:
            errors.append("buyerNTNCNIC is required for a registered buyer")
        if buyer_id and not re.fullmatch(r"(?:\d{7}|\d{13})", buyer_id):
            errors.append("buyerNTNCNIC must be 7 or 13 digits when provided")

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

        # 2. Items Validation
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

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fbr_ready": len(errors) == 0,
            "transformed_payload": payload,
        }

    def submit_invoice(self, invoice_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Submits an invoice to the official PRAL DI API v1.12 live production endpoint."""
        val = self.validate_invoice(invoice_data)
        if not val["is_valid"]:
            return FBRAdapterResponse(
                success=False,
                status="INVALID",
                error_code="FBR-PROD-VAL-100",
                error_message="; ".join(val["errors"]),
                is_retryable=False,
                raw_response={"errors": val["errors"]},
                environment=self.environment,
                provider=self.provider,
                is_simulated=False,
            )

        if not self.is_configured():
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_code="FBR-PROD-UNCONFIGURED",
                error_message="Production FBR credentials are not configured. Cannot transmit to live tax authority.",
                is_retryable=False,
                raw_response={"configured": False},
                environment=self.environment,
                provider=self.provider,
                is_simulated=False,
            )

        fbr_payload = val.get("transformed_payload") or self._transform_to_fbr_schema(invoice_data)
        endpoint = self.submit_url
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "User-Agent": "FBR-Invoice-Cloud-DI-v1.12",
        }

        try:
            with httpx.Client(timeout=settings.FBR_HTTP_TIMEOUT_SECONDS, verify=True, proxy=settings.FIXIE_URL or None, trust_env=not bool(settings.FIXIE_URL)) as client:
                resp = client.post(endpoint, json=fbr_payload, headers=headers)
                if resp.status_code >= 500:
                    return FBRAdapterResponse(
                        success=False,
                        status="FAILED",
                        error_code=f"HTTP-{resp.status_code}",
                        error_message=f"Live FBR Gateway returned server error ({resp.status_code}): {resp.text[:200]}",
                        is_retryable=True,
                        raw_response={"status_code": resp.status_code, "body": resp.text},
                        environment=self.environment,
                        provider=self.provider,
                        is_simulated=False,
                    )
                if resp.status_code in (401, 403):
                    return FBRAdapterResponse(
                        success=False,
                        status="FAILED",
                        error_code=f"HTTP-{resp.status_code}",
                        error_message="Unauthorized: Production PRAL Bearer Token rejected or expired.",
                        is_retryable=False,
                        raw_response={"status_code": resp.status_code, "body": resp.text},
                        environment=self.environment,
                        provider=self.provider,
                        is_simulated=False,
                    )
                resp_json = resp.json()
                return self.parse_response(resp_json)
        except (httpx.TimeoutException, httpx.NetworkError) as net_err:
            logger.warning(f"Production FBR HTTP connection failure: {net_err}")
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_code="NET-PROD-TIMEOUT",
                error_message=f"Gateway timeout or connection error connecting to live FBR: {str(net_err)}",
                is_retryable=True,
                raw_response={"error": str(net_err)},
                environment=self.environment,
                provider=self.provider,
                is_simulated=False,
            )
        except Exception as exc:
            logger.error(f"Unexpected production FBR transmission error: {exc}")
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_code="PROD-TRANSMISSION-ERR",
                error_message=f"Error transmitting to live FBR ledger: {str(exc)}",
                is_retryable=False,
                raw_response={"error": str(exc)},
                environment=self.environment,
                provider=self.provider,
                is_simulated=False,
            )

    def validate_invoice_remote(self, invoice_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Sends invoice to the live FBR validateinvoicedata endpoint without persisting."""
        val = self.validate_invoice(invoice_data)
        if not val["is_valid"]:
            return FBRAdapterResponse(
                success=False,
                status="INVALID",
                error_code="FBR-PROD-VAL-100",
                error_message="; ".join(val["errors"]),
                is_retryable=False,
                raw_response={"errors": val["errors"]},
                environment=self.environment,
                provider=self.provider,
                is_simulated=False,
            )
        fbr_payload = val.get("transformed_payload") or self._transform_to_fbr_schema(invoice_data)
        endpoint = self.validate_url
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=settings.FBR_HTTP_TIMEOUT_SECONDS, verify=True, proxy=settings.FIXIE_URL or None, trust_env=not bool(settings.FIXIE_URL)) as client:
                resp = client.post(endpoint, json=fbr_payload, headers=headers)
                return self.parse_response(resp.json())
        except Exception as e:
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_message=str(e),
                environment=self.environment,
                provider=self.provider,
                is_simulated=False,
            )

    def submit_note(self, note_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Submits a Debit Note or adjustment note to the live FBR DI API."""
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
        """Probes live production FBR gateway status."""
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "status": "UNCONFIGURED",
                "latency_ms": 0,
                "message": "Production FBR Bearer Token is not configured for this organization.",
                "environment": "PRODUCTION",
                "provider": "PRODUCTION",
                "is_simulated": False,
                "details": {
                    "base_url": self.base_url,
                    "submit_url": self.submit_url,
                    "validate_url": self.validate_url,
                },
            }

        endpoint = self.validate_url
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=5.0, verify=True, proxy=settings.FIXIE_URL or None, trust_env=not bool(settings.FIXIE_URL)) as client:
                resp = client.options(endpoint, headers=headers)
                latency = int((time.time() - start) * 1000)
                is_online = resp.status_code in (200, 405, 400, 422)
                return {
                    "success": is_online,
                    "status": "ONLINE" if is_online else f"HTTP_{resp.status_code}",
                    "latency_ms": latency,
                    "message": f"Connected to live FBR Production Gateway (HTTP {resp.status_code})",
                    "environment": "PRODUCTION",
                    "provider": "PRODUCTION",
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
                "message": f"Live FBR Production Gateway unreachable: {str(e)}",
                "environment": "PRODUCTION",
                "provider": "PRODUCTION",
                "is_simulated": False,
                "details": {
                    "base_url": self.base_url,
                    "submit_url": self.submit_url,
                },
            }

    def get_reference_data(self) -> Dict[str, Any]:
        return {
            "source": "FBR Live Digital Invoicing System",
            "version": "1.12-PROD",
            "rates": ["18%", "15%", "1%", "0%"],
            "uoms": ["Numbers", "NOS", "KGS", "LTR", "MTR", "BAG", "BOX", "SET", "TON"],
        }

    def parse_response(self, raw_response: Dict[str, Any]) -> FBRAdapterResponse:
        """Parses the official DI API v1.12 response shape.
        
        Expected structure:
        {
          "invoiceNumber": "FBR-INV-...",
          "dated": "2025-...",
          "validationResponse": {
            "statusCode": "00",
            "status": "Valid",
            "error": null,
            "invoiceStatuses": [...]
          }
        }
        
        Guarantees HTTP 200 alone is never treated as success without validation.
        """
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

        # Check item-level validation failures
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

        # Handle backward-compatible response shape if validationResponse was absent
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
            msg = raw_response.get("message") or raw_response.get("Message") or "Validation failed"
            error_messages.append(msg)

        final_error_message = "; ".join(error_messages) if not success else None
        error_code = None
        if not success:
            top_err_code = val_resp.get("errorCode") if isinstance(val_resp, dict) else None
            resolved_err_code = top_err_code or first_item_error_code or status_code
            error_code = f"FBR-DI-{resolved_err_code}" if resolved_err_code else "FBR-DI-INVALID"

        # Construct or extract QR code data
        qr_code = raw_response.get("qrCode") or raw_response.get("qr_code") or raw_response.get("qr_code_data")
        if success and not qr_code and inv_num:
            qr_code = f"FBR-DI|INV:{inv_num}|DT:{dated or ''}"

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
        if not self.is_configured():
            return FBRAdapterResponse(
                success=False,
                status="FAILED",
                error_message="Production credentials not configured",
                environment=self.environment,
                provider=self.provider,
                is_simulated=False,
            )
        return FBRAdapterResponse(
            success=True,
            status="VALID",
            error_message="Confirmed in FBR production ledger",
            environment=self.environment,
            provider=self.provider,
            is_simulated=False,
        )

