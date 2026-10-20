"""Credential-aware PRAL reference access probe, independent of invoice submission."""
import time
import httpx

from backend.app.core.config import settings

PRAL_PROVINCES_URL = "https://gw.fbr.gov.pk/pdi/v1/provinces"


def probe_pral_reference(token: str, environment: str = "SANDBOX") -> dict:
    """Authenticate against a read-only PRAL endpoint.

    Success proves bearer-token access to reference data, NOT permission to
    create production invoices or that any invoice was submitted.
    """
    started = time.monotonic()
    result = {
        "success": False,
        "status": "UNCONFIGURED",
        "environment": environment,
        "provider": environment,
        "is_simulated": False,
        "authenticated_reference_access": False,
        "invoice_submission_verified": False,
    }
    if not token or not token.strip():
        return {**result, "message": "FBR Bearer token is missing."}

    try:
        with httpx.Client(
            timeout=settings.FBR_HTTP_TIMEOUT_SECONDS,
            proxy=settings.FIXIE_URL or None,
            trust_env=not bool(settings.FIXIE_URL),
        ) as client:
            resp = client.get(
                PRAL_PROVINCES_URL,
                headers={"Authorization": f"Bearer {token.strip()}", "Accept": "application/json"},
            )
        latency = int((time.monotonic() - started) * 1000)
        if resp.status_code in (401, 403):
            return {**result, "status": "AUTH_FAILED",
                    "latency_ms": latency, "message": "PRAL rejected the Bearer token."}
        if resp.status_code != 200:
            return {**result, "status": "CONNECTION_UNAVAILABLE",
                    "latency_ms": latency,
                    "message": f"PRAL reference endpoint returned HTTP {resp.status_code}."}
        payload = resp.json()
        if not isinstance(payload, list):
            return {**result, "status": "INVALID_RESPONSE", "latency_ms": latency,
                    "message": "PRAL reference endpoint returned an unexpected response."}
        return {**result, "success": True, "status": "REFERENCE_ACCESS_VERIFIED",
                "authenticated_reference_access": True, "latency_ms": latency,
                "message": "PRAL Bearer token accessed the official reference API. Invoice submission is not verified."}
    except (httpx.HTTPError, ValueError) as exc:
        return {**result, "status": "CONNECTION_UNAVAILABLE",
                "latency_ms": int((time.monotonic() - started) * 1000),
                "message": f"PRAL reference check failed ({type(exc).__name__})."}
