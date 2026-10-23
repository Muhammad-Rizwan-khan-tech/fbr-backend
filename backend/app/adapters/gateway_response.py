"""Safe, conservative decoding of official FBR gateway responses.

HTTP 200 alone is not fiscal acceptance. Only documented invoice response
objects with valid nested validation status can ever be accepted.
"""
import hashlib
import json
import re
from typing import Any, Dict, Optional, Tuple


def _redact(text: str) -> str:
    text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", text)
    text = re.sub(
        r"(?i)(?:api[_-]?key|access[_-]?token|authorization|password|secret)\s*[:=]\s*[^\s,;]+",
        "[REDACTED_CREDENTIAL]", text,
    )
    text = re.sub(r"(?<!\d)\d{7,13}(?!\d)", "[TAX_ID]", text)
    text = re.sub(r"\b[A-Za-z0-9_./-]{28,}\b", "[REDACTED_VALUE]", text)
    return text[:240]


def inspect_gateway_response(response: Any) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Return a response dict only when the gateway actually gave an object.

    Some gateways/proxies return HTML, empty data, JSON arrays, or a
    double-encoded JSON string even with HTTP 200. Preserve safe diagnostics
    without guessing an invoice number or storing potentially secret bodies.
    """
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("content-type", "")).split(";", 1)[0].lower()[:80]
    raw_text = getattr(response, "text", "") or ""
    if not isinstance(raw_text, str):
        raw_text = ""
    diagnostic = {
        "http_status": getattr(response, "status_code", None),
        "content_type": content_type or "unknown",
        "body_chars": len(raw_text),
        "body_sha256_prefix": hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16],
    }

    try:
        decoded = response.json()
    except (ValueError, TypeError):
        decoded = None

    # Decode string-wrapped JSON once or twice, without treating arbitrary
    # string responses like accepted invoices.
    depth = 0
    while isinstance(decoded, str) and depth < 2:
        stripped = decoded.strip()
        if not stripped.startswith(("{", "[")):
            break
        try:
            decoded = json.loads(stripped)
        except ValueError:
            break
        depth += 1

    if isinstance(decoded, dict):
        diagnostic["response_kind"] = "json_object" if depth == 0 else "wrapped_json_object"
        return decoded, diagnostic

    if isinstance(decoded, list):
        diagnostic["response_kind"] = "json_array"
        diagnostic["array_items"] = len(decoded)
        # Arrays do not satisfy the documented invoice submission contract.
        if decoded and isinstance(decoded[0], dict):
            diagnostic["gateway_hint"] = _redact(str(
                decoded[0].get("message") or decoded[0].get("error") or decoded[0].get("detail") or ""
            ))
    elif isinstance(decoded, str):
        diagnostic["response_kind"] = "json_string"
        diagnostic["gateway_hint"] = _redact(decoded)
    elif raw_text.lstrip().lower().startswith(("<!doctype html", "<html")) or "html" in content_type:
        diagnostic["response_kind"] = "html"
    elif not raw_text.strip():
        diagnostic["response_kind"] = "empty"
    elif decoded is None and raw_text.strip().lower() == "null":
        diagnostic["response_kind"] = "json_null"
    elif decoded is None:
        diagnostic["response_kind"] = "non_json_text"
        diagnostic["gateway_hint"] = _redact(raw_text)
    else:
        diagnostic["response_kind"] = "json_" + type(decoded).__name__
    if not diagnostic.get("gateway_hint"):
        diagnostic.pop("gateway_hint", None)
    return None, diagnostic
