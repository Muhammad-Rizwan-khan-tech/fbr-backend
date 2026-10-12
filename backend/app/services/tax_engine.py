from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple


class TaxCalculationError(Exception):
    pass


class PakistanTaxEngine:
    """
    Pakistan Tax Engine implementing FBR digital invoicing calculation rules.
    - Deterministic rounding (ROUND_HALF_UP, 2 decimal places)
    - Sales Tax calculation over taxable amounts
    - Validates bounds and consistency
    """

    @staticmethod
    def round_currency(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_line_item(
        cls,
        quantity: Decimal,
        unit_price: Decimal,
        discount: Decimal = Decimal("0.00"),
        tax_rate_percent: Decimal = Decimal("18.00")
    ) -> Dict[str, Decimal]:
        if quantity <= Decimal("0"):
            raise TaxCalculationError("Quantity must be greater than zero")
        if unit_price < Decimal("0"):
            raise TaxCalculationError("Unit price cannot be negative")
        if discount < Decimal("0"):
            raise TaxCalculationError("Discount cannot be negative")
        if tax_rate_percent < Decimal("0"):
            raise TaxCalculationError("Tax rate cannot be negative")

        gross_amount = cls.round_currency(quantity * unit_price)
        
        if discount > gross_amount:
            raise TaxCalculationError(f"Discount ({discount}) cannot exceed line gross amount ({gross_amount})")
        
        taxable_amount = cls.round_currency(gross_amount - discount)
        tax_amount = cls.round_currency(taxable_amount * (tax_rate_percent / Decimal("100.00")))
        line_total = cls.round_currency(taxable_amount + tax_amount)

        return {
            "gross_amount": gross_amount,
            "discount": discount,
            "taxable_amount": taxable_amount,
            "tax_amount": tax_amount,
            "line_total": line_total
        }

    @classmethod
    def calculate_invoice_totals(
        cls,
        items: List[Dict[str, Any]],
        other_charges: Decimal = Decimal("0.00")
    ) -> Dict[str, Decimal]:
        if not items:
            raise TaxCalculationError("Invoice must have at least one line item")

        subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        taxable_amount = Decimal("0.00")
        total_tax = Decimal("0.00")

        for idx, item in enumerate(items, 1):
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("unit_price", 0)))
            disc = Decimal(str(item.get("discount", 0)))
            rate = Decimal(str(item.get("tax_rate", 18.00)))

            line_res = cls.calculate_line_item(qty, price, disc, rate)
            subtotal += line_res["gross_amount"]
            total_discount += line_res["discount"]
            taxable_amount += line_res["taxable_amount"]
            total_tax += line_res["tax_amount"]

        subtotal = cls.round_currency(subtotal)
        total_discount = cls.round_currency(total_discount)
        taxable_amount = cls.round_currency(taxable_amount)
        total_tax = cls.round_currency(total_tax)
        other_charges = cls.round_currency(Decimal(str(other_charges)))
        grand_total = cls.round_currency(taxable_amount + total_tax + other_charges)

        return {
            "subtotal": subtotal,
            "total_discount": total_discount,
            "taxable_amount": taxable_amount,
            "total_tax": total_tax,
            "other_charges": other_charges,
            "grand_total": grand_total
        }
