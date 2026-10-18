"""Official PRAL / FBR Digital Invoicing API v1.12 Request & Response Schemas.
Sourced from Technical Specification for DI API — User Manual, Version 1.12:
  - Section 4.1: Invoice Posting Request & Response (pp. 7–14)
  - Section 4.2: Invoice Validation Request & Response (pp. 15–22)
"""

from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class PRALInvoiceItem(BaseModel):
    """Line item schema strictly adhering to PRAL DI API v1.12 item properties."""
    hsCode: str = Field(..., description="8-digit Pakistan Customs Tariff / HS Code")
    productDescription: str = Field(..., description="Item or service description")
    rate: str = Field(..., description="Statutory tax rate formatted as string (e.g. '18%', '0%')")
    uoM: str = Field(..., description="Unit of measurement from official PRAL UOM table")
    quantity: Decimal = Field(..., description="Numeric quantity supplied")
    totalValues: Decimal = Field(..., description="Gross item value before discount")
    valueSalesExcludingST: Decimal = Field(..., description="Taxable value of supplies excluding sales tax")
    fixedNotifiedValueOrRetailPrice: Decimal = Field(default=Decimal("0.00"), description="Fixed notified value or retail price if applicable")
    salesTaxApplicable: Decimal = Field(..., description="Calculated statutory sales tax amount")
    salesTaxWithheldAtSource: Decimal = Field(default=Decimal("0.00"), description="Sales tax withheld at source")
    extraTax: Decimal = Field(default=Decimal("0.00"), description="Extra tax amount if applicable")
    furtherTax: Decimal = Field(default=Decimal("0.00"), description="Further tax amount for unregistered buyers")
    sroScheduleNo: Optional[str] = Field(default=None, description="SRO schedule reference if claiming concession")
    fedPayable: Decimal = Field(default=Decimal("0.00"), description="Federal Excise Duty payable")
    discount: Decimal = Field(default=Decimal("0.00"), description="Line item trade discount")
    saleType: str = Field(..., description="Transaction sale type description from PRAL reference table")
    sroItemSerialNo: Optional[str] = Field(default=None, description="SRO item serial number if claiming concession")

    @field_validator("hsCode")
    @classmethod
    def validate_hs_code(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 4:
            raise ValueError("hsCode must be at least 4 digits; standard is 8-digit format.")
        return clean

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class PRALInvoiceHeader(BaseModel):
    """Header and root document schema for PRAL DI API v1.12 invoice transmission."""
    invoiceType: str = Field(..., description="Document type: 'Sale Invoice' or 'Debit Note'")
    invoiceDate: str = Field(..., description="Transaction date formatted as YYYY-MM-DD")
    sellerNTNCNIC: str = Field(..., description="Seller 7-digit NTN or 13-digit CNIC")
    sellerBusinessName: str = Field(..., description="Seller registered business legal name")
    sellerProvince: str = Field(..., description="Seller province from PRAL reference table")
    sellerAddress: str = Field(..., description="Seller physical address")
    buyerNTNCNIC: Optional[str] = Field(default=None, description="Buyer 7-digit NTN or 13-digit CNIC (1111111 if unregistered)")
    buyerBusinessName: str = Field(..., description="Buyer business name or customer name")
    buyerProvince: str = Field(..., description="Buyer province from PRAL reference table")
    buyerAddress: str = Field(..., description="Buyer physical address")
    buyerRegistrationType: str = Field(..., description="'Registered' or 'Unregistered'")
    invoiceRefNo: Optional[str] = Field(default=None, description="Original invoice reference number (mandatory for Debit Notes)")
    scenarioId: Optional[str] = Field(default=None, description="Sandbox scenario identifier (^SN\\d{3}$) — strictly omitted in Production")
    items: List[PRALInvoiceItem] = Field(..., description="Array of line items (at least 1 item required)")

    @field_validator("invoiceType")
    @classmethod
    def validate_invoice_type(cls, v: str) -> str:
        clean = v.strip()
        if clean not in ("Sale Invoice", "Debit Note"):
            raise ValueError("invoiceType must be exactly 'Sale Invoice' or 'Debit Note'.")
        return clean

    @field_validator("buyerRegistrationType")
    @classmethod
    def validate_buyer_reg_type(cls, v: str) -> str:
        clean = v.strip()
        if clean not in ("Registered", "Unregistered"):
            raise ValueError("buyerRegistrationType must be 'Registered' or 'Unregistered'.")
        return clean

    def serialize_for_environment(self, environment: str = "PRODUCTION") -> Dict[str, Any]:
        """Serializes payload into dict, strictly omitting scenarioId in Production environment."""
        data = self.model_dump(mode="json")
        if environment.upper() == "PRODUCTION":
            data.pop("scenarioId", None)
        return data


class PRALItemStatus(BaseModel):
    itemSNo: int
    statusCode: str
    status: str
    errorCode: Optional[str] = None
    error: Optional[str] = None


class PRALResponse(BaseModel):
    """Normalized response schema parsing PRAL DI API v1.12 response payload."""
    invoiceNumber: Optional[str] = None
    dated: Optional[str] = None
    validationResponse: Optional[str] = None
    statusCode: Optional[str] = None
    status: Optional[str] = None  # "Valid", "Invalid"
    errorCode: Optional[str] = None
    error: Optional[str] = None
    invoiceStatuses: List[PRALItemStatus] = []
    raw_response: Dict[str, Any] = {}

    @property
    def is_fbr_accepted(self) -> bool:
        """Determines if PRAL confirmed authoritative fiscal acceptance."""
        status_norm = (self.status or self.validationResponse or "").strip().lower()
        code_norm = (self.statusCode or "").strip()
        return status_norm == "valid" or code_norm in ("00", "200", "valid")
