"""Validated seller NTN/CNIC formatting for PRAL invoice payloads.

FBR DI expects a 7-digit company NTN or a 13-digit CNIC. An NTN entered
with one trailing check digit may be written as 1234567-8 or 12345678.
Strip only that single check digit; reject all other invalid lengths instead
of truncating arbitrary data. This formatting does not verify registration.
Do not silently truncate malformed values or manufacture an NTN.
"""
import re

def normalize_seller_tax_id(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{7}", text):
        return text
    if re.fullmatch(r"\d{7}-\d", text):
        return text[:7]
    if re.fullmatch(r"\d{8}", text):
        # Legacy admin panels sometimes remove the NTN check-digit separator.
        # Convert only the exact 8-digit form into FBR DI's 7-digit NTN field.
        return text[:7]
    if re.fullmatch(r"\d{13}", text):
        return text
    if re.fullmatch(r"\d{5}-\d{7}-\d", text):
        return text.replace("-", "")
    raise ValueError("Seller NTN must be 7 digits (optional eighth check digit) or a 13-digit CNIC")

def is_incomplete_tax_profile(ntn: str | None, address: str | None, province: str | None) -> bool:
    try:
        cleaned = normalize_seller_tax_id(ntn)
    except ValueError:
        return True
    return cleaned in ("", "1000000") or not address or address.strip().lower() in ("pakistan", "n/a") or not province or not province.strip()
