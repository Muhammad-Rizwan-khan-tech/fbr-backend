"""Non-mutating FBR / PRAL authentication check against an official reference API.

A successful proxy/IP check or OPTIONS request is NOT authentication verification.
This GET never submits a tax invoice.
"""
import time
from typing import Any, Dict

import httpx

from backend.app.core.config import settings

PROVINCES_URL = "https://gw.fbr.gov.pk/pdi/v1/provinces"


def check_fbr_token(token: str) -> Dict[str, Any]:
    if not token or not token.strip():
        return {
            "success": False, "status": "UNCONFIGURED", "latency_ms": 0,
            "message": "No FBR security token configured",
        }

    start = time.monotonic()
    try:
        with httpx.Client(
            timeout=settings.FBR_HTTP_TIMEOUT_SECONDS,
            proxy=settings.FIXIE_URL or None,
            trust_env=not bool(settings.FIXIE_URL),
        ) as client:
            resp = client.get(PROVINCES_URL, headers={
                "Authorization": f"Bearer {token.strip()}",
                "Accept": "application/json",
            })

        if resp.status_code in (401, 403):
            status, message = "AUTH_FAILED", "FBR rejected the token (HTTP 401/403)"
        elif resp.status_code != 200:
            status, message = "CONNECTION_UNAVAILABLE", f"FBR reference API returned HTTP {resp.status_code}"
        else:
            body: Any = resp.json()
            valid = (
                isinstance(body, list)
                and bool(body)
                and isinstance(body[0], dict)
                and "stateProvinceCode" in body[0]
            )
            status = "VERIFIED" if valid else "UNEXPECTED_RESPONSE"
            message = (
                "Token authenticated against official FBR province reference API"
                if valid else "FBR returned an unexpected province reference payload"
            )

    except (httpx.HTTPError, ValueError):
        status, message = "CONNECTION_UNAVAILABLE", "Could not validate token against FBR reference API"

    return {
        "success": status == "VERIFIED",
        "status": status,
        "latency_ms": int((time.monotonic() - start) * 1000),
        "message": message,
    }
