"""Conditional empty extraTax serialization for reduced-rate supplies (0091)."""
import re
from decimal import Decimal, InvalidOperation


def is_reduced_rate(sale_type):
    normalized = re.sub(r'[^a-z]', '', str(sale_type or '').lower())
    return normalized == 'reduced' or 'reducedrate' in normalized


def extra_tax_wire_value(sale_type, raw):
    amount = Decimal(str(raw if raw is not None and raw != '' else 0))
    # This gateway rejects numeric zero (0091) and a missing key (0300).
    # The reduced-rate exception uses an explicit empty string; other tax fields
    # remain numeric. Do not drop a non-zero financial amount.
    if is_reduced_rate(sale_type) and amount == 0:
        return ""
    return float(round(amount, 2))


def reduced_extra_tax_errors(items):
    errors = []
    for index, item in enumerate(items or [], 1):
        def value(camel, snake):
            if isinstance(item, dict):
                return item.get(camel) if item.get(camel) is not None else item.get(snake)
            return getattr(item, snake, None)
        if not is_reduced_rate(value('saleType', 'sale_type')):
            continue
        raw = value('extraTax', 'extra_tax')
        try:
            amount = Decimal(str(raw if raw is not None and raw != '' else 0))
            invalid = not amount.is_finite() or amount != 0
        except (InvalidOperation, ValueError):
            invalid = True
        if invalid:
            errors.append(f'Item {index}: [0091] Extra tax is not applicable to Goods at Reduced Rate. Correct the extra tax or the sale classification before submission; amounts are never silently removed.')
    return errors
