"""Official PRAL / FBR Digital Invoicing API v1.12 Error Code Registry.
Sourced from Technical Specification for DI API — User Manual, Version 1.12:
  - Section 7: Sales Error Codes (pp. 36–41)
  - Section 8: Purchase Error Codes (pp. 42–45)
"""

from typing import Dict, Any, Optional

class PRALErrorCode:
    def __init__(
        self,
        code: str,
        category: str,
        description: str,
        human_explanation: str,
        related_field: Optional[str] = None,
        recommended_action: str = "",
        is_operational_failure: bool = False,
    ):
        self.code = code
        self.category = category  # SALES | PURCHASE | AUTH | SYSTEM
        self.description = description
        self.human_explanation = human_explanation
        self.related_field = related_field
        self.recommended_action = recommended_action
        self.is_operational_failure = is_operational_failure

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "description": self.description,
            "human_explanation": self.human_explanation,
            "related_field": self.related_field,
            "recommended_action": self.recommended_action,
            "is_operational_failure": self.is_operational_failure,
        }


PRAL_ERROR_REGISTRY: Dict[str, PRALErrorCode] = {
    "0091": PRALErrorCode(
        code="0091", category="SALES", description="Extra tax must be empty for reduced-rate goods",
        human_explanation="The gateway requires an empty extraTax value for reduced-rate supplies; numeric zero and a missing key can be rejected.",
        related_field="extraTax",
        recommended_action="Keep reduced-rate extra tax at zero internally and send an explicit empty extraTax string in the FBR request. Correct non-zero tax or the sale classification before resubmitting.",
    ),
    # Authentication & Security Errors (Section 3.1 & 7)
    "0401": PRALErrorCode(
        code="0401",
        category="AUTH",
        description="Invalid Authorization Token or Expired PRAL Bearer Token",
        human_explanation="The FBR integration token provided in the Authorization header is invalid, unverified, or has expired its 5-year validity period.",
        related_field="Authorization",
        recommended_action="Renew or configure a valid PRAL Bearer Token in the Laravel Super Admin Panel.",
        is_operational_failure=True,
    ),
    "0402": PRALErrorCode(
        code="0402",
        category="AUTH",
        description="Seller NTN/CNIC does not match authorized Token Taxpayer Registration",
        human_explanation="The seller NTN or CNIC specified in the invoice payload does not match the organization registration authorized for this PRAL integration token.",
        related_field="sellerNTNCNIC",
        recommended_action="Verify that the Seller NTN in organization settings strictly matches the NTN issued on the PRAL onboarding certificate.",
        is_operational_failure=False,
    ),

    # Document Header & Date Errors (pp. 36–37)
    "0001": PRALErrorCode(
        code="0001",
        category="SALES",
        description="Invalid Invoice Type specified",
        human_explanation="The invoice type is not recognized by PRAL. Only 'Sale Invoice' and 'Debit Note' are permitted.",
        related_field="invoiceType",
        recommended_action="Select either 'Sale Invoice' or 'Debit Note'.",
    ),
    "0002": PRALErrorCode(
        code="0002",
        category="SALES",
        description="Invalid or future Invoice Date",
        human_explanation="The invoice date format is incorrect or the date is in the future. Required format: YYYY-MM-DD.",
        related_field="invoiceDate",
        recommended_action="Provide a valid date formatted as YYYY-MM-DD on or before the current date.",
    ),
    "0003": PRALErrorCode(
        code="0003",
        category="SALES",
        description="Missing Reference Invoice Number for Debit Note",
        human_explanation="Debit Notes strictly require an original invoice reference number (invoiceRefNo).",
        related_field="invoiceRefNo",
        recommended_action="Specify the original Sale Invoice number being adjusted in invoiceRefNo.",
    ),

    # Taxpayer Registration Errors (pp. 37–38)
    "0101": PRALErrorCode(
        code="0101",
        category="SALES",
        description="Seller NTN/CNIC is missing or invalid format",
        human_explanation="The Seller NTN must be a 7-digit numeric code or a 13-digit CNIC.",
        related_field="sellerNTNCNIC",
        recommended_action="Enter a valid 7-digit NTN or 13-digit CNIC for the Seller.",
    ),
    "0102": PRALErrorCode(
        code="0102",
        category="SALES",
        description="Seller is not registered on the Active Taxpayer List (ATL)",
        human_explanation="The Seller NTN is inactive or blacklisted in the FBR Sales Tax database.",
        related_field="sellerNTNCNIC",
        recommended_action="Check the Seller ATL status on the FBR IRIS / STATL portal before submitting invoices.",
    ),
    "0103": PRALErrorCode(
        code="0103",
        category="SALES",
        description="Buyer NTN/CNIC is required for Registered Buyer",
        human_explanation="When buyerRegistrationType is 'Registered', a valid 7-digit NTN or 13-digit CNIC must be provided.",
        related_field="buyerNTNCNIC",
        recommended_action="Enter the Buyer's valid NTN or switch registration type to 'Unregistered'.",
    ),
    "0104": PRALErrorCode(
        code="0104",
        category="SALES",
        description="Buyer Registration Type is invalid",
        human_explanation="buyerRegistrationType must be either 'Registered' or 'Unregistered'.",
        related_field="buyerRegistrationType",
        recommended_action="Ensure buyerRegistrationType is set to 'Registered' or 'Unregistered'.",
    ),
    "0105": PRALErrorCode(
        code="0105",
        category="SALES",
        description="Buyer province is invalid",
        human_explanation="The specified buyer province is not in the PRAL official province reference table.",
        related_field="buyerProvince",
        recommended_action="Select a valid province from the PRAL reference list (e.g. Punjab, Sindh, etc.).",
    ),

    # Line Item, HS Code & Rate Errors (pp. 38–40)
    "0201": PRALErrorCode(
        code="0201",
        category="SALES",
        description="Invalid 8-digit HS Code",
        human_explanation="The line item HS Code (Pakistan Customs Tariff code) is invalid or does not exist in the PRAL reference table.",
        related_field="hsCode",
        recommended_action="Select a valid 8-digit Pakistan HS Code from the PRAL reference API.",
    ),
    "0202": PRALErrorCode(
        code="0202",
        category="SALES",
        description="Incompatible Unit of Measurement (UOM) for HS Code",
        human_explanation="The selected Unit of Measurement (uoM) is not legally permitted for this specific HS Code.",
        related_field="uoM",
        recommended_action="Consult the PRAL HS_UOM reference API and select an approved UOM.",
    ),
    "0203": PRALErrorCode(
        code="0203",
        category="SALES",
        description="Applicable Sales Tax Rate does not match official schedule",
        human_explanation="The tax rate specified is not recognized for this Sale Type, Province, and Item classification.",
        related_field="rate",
        recommended_action="Select an authorized tax rate from the PRAL SaleTypeToRate reference API.",
    ),
    "0204": PRALErrorCode(
        code="0204",
        category="SALES",
        description="Quantity must be greater than zero",
        human_explanation="Line item quantity cannot be zero or negative.",
        related_field="quantity",
        recommended_action="Enter a positive numeric quantity.",
    ),
    "0205": PRALErrorCode(
        code="0205",
        category="SALES",
        description="Invalid Sale Type specified",
        human_explanation="The line item saleType is not recognized in the PRAL transaction types table.",
        related_field="saleType",
        recommended_action="Select a recognized sale type (e.g. Goods at standard rate, Services, etc.).",
    ),
    "0206": PRALErrorCode(
        code="0206",
        category="SALES",
        description="Missing SRO Item Serial Number for SRO Schedule",
        human_explanation="When claiming an SRO concession (sroScheduleNo), sroItemSerialNo is mandatory.",
        related_field="sroItemSerialNo",
        recommended_action="Select the valid SRO Item Serial Number from the SROItem reference API.",
    ),

    # Calculation & Financial Errors (pp. 40–41)
    "0301": PRALErrorCode(
        code="0301",
        category="SALES",
        description="Arithmetic mismatch: totalValues does not equal quantity * unit price",
        human_explanation="The calculated gross total does not match the product of quantity and unit price.",
        related_field="totalValues",
        recommended_action="Ensure totalValues = quantity * unit_price using deterministic 2-decimal rounding.",
    ),
    "0302": PRALErrorCode(
        code="0302",
        category="SALES",
        description="Arithmetic mismatch: valueSalesExcludingST does not equal totalValues - discount",
        human_explanation="Taxable sales value must equal gross values minus line-item discount.",
        related_field="valueSalesExcludingST",
        recommended_action="Ensure valueSalesExcludingST = totalValues - discount.",
    ),
    "0303": PRALErrorCode(
        code="0303",
        category="SALES",
        description="Arithmetic mismatch: salesTaxApplicable does not match rate * valueSalesExcludingST",
        human_explanation="The calculated sales tax amount differs from the statutory rate applied to the taxable value.",
        related_field="salesTaxApplicable",
        recommended_action="Re-calculate sales tax using PakistanTaxEngine with ROUND_HALF_UP precision.",
    ),

    # Purchase & Input Tax Errors (Section 8, pp. 42–45)
    "0501": PRALErrorCode(
        code="0501",
        category="PURCHASE",
        description="Supplier NTN is not active on ATL for Input Tax adjustment",
        human_explanation="Input tax deduction cannot be claimed against an inactive or non-compliant supplier NTN.",
        related_field="sellerNTNCNIC",
        recommended_action="Verify supplier compliance status on the FBR portal.",
    ),
    "0502": PRALErrorCode(
        code="0502",
        category="PURCHASE",
        description="Duplicate purchase invoice claimed",
        human_explanation="This purchase invoice reference has already been claimed in a previous tax period.",
        related_field="invoiceRefNo",
        recommended_action="Check purchase records for duplicate invoice entry.",
    ),

    # System & Network Errors
    "0500": PRALErrorCode(
        code="0500",
        category="SYSTEM",
        description="PRAL Internal Gateway Server Error",
        human_explanation="The FBR / PRAL digital invoicing gateway encountered an internal server exception.",
        recommended_action="Do not alter payload; verify gateway status and retry after exponential backoff.",
        is_operational_failure=True,
    ),
    "0504": PRALErrorCode(
        code="0504",
        category="SYSTEM",
        description="PRAL Gateway Timeout (504)",
        human_explanation="The PRAL digital invoicing gateway timed out before returning a definitive fiscal confirmation.",
        recommended_action="Do not re-submit with a new reference immediately; check submission reconciliation to avoid duplicate invoices.",
        is_operational_failure=True,
    ),
}


def lookup_pral_error(code: Optional[str]) -> Optional[PRALErrorCode]:
    """Retrieves structured error metadata by error code."""
    if not code:
        return None
    code_str = str(code).strip()
    return PRAL_ERROR_REGISTRY.get(code_str)


def format_pral_error_message(code: Optional[str], default_msg: str = "") -> str:
    """Returns a user-friendly and actionable explanation for a PRAL error code."""
    meta = lookup_pral_error(code)
    if meta:
        return f"[{meta.code}] {meta.human_explanation} Recommended Action: {meta.recommended_action}"
    return default_msg or f"Error Code: {code}"
