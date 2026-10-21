"""Validated seller NTN/CNIC formatting for PRAL invoice payloads.

A company NTN uses seven digits (optionally followed by a check digit as
1234567-8); a CNIC uses thirteen digits, optionally with two hyphens.
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
    if re.fullmatch(r"\d{13}", text):
        return text
    if re.fullmatch(r"\d{5}-\d{7}-\d", text):
        return text.replace("-", "")
    raise ValueError("Seller NTN must be 7 digits (optional -check digit) or a 13-digit CNIC")

def is_incomplete_tax_profile(ntn: str | None, address: str | None, province: str | None) -> bool:
    try:
        cleaned = normalize_seller_tax_id(ntn)
    except ValueError:
        return True
    return cleaned in ("", "1000000") or not address or address.strip().lower() in ("pakistan", "n/a") or not province or not province.strip()
