"""Canonical FBR 8-digit HS codes, preserving leading zeros."""
import re


def normalize_hs_code(value):
    raw = str(value or "").strip()
    if re.fullmatch(r"(?:[0-9]{8}|[0-9]{4}\.[0-9]{4}|[0-9]{4}\.[0-9]{2}\.[0-9]{2})", raw):
        digits = raw.replace(".", "")
        return digits[:4] + "." + digits[4:]
    return raw


def valid_hs_code(value):
    return bool(re.fullmatch(r"[0-9]{4}\.[0-9]{4}", normalize_hs_code(value)))
