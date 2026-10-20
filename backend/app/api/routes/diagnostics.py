"""Read-only outbound proxy diagnostic. No FBR submission is performed."""
import logging

import httpx
from fastapi import APIRouter, HTTPException

from backend.app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


@router.get("/outbound-ip")
async def outbound_ip():
    """Report the egress IP from a request explicitly routed through Fixie."""
    if not settings.FIXIE_URL:
        raise HTTPException(
            status_code=503,
            detail="FIXIE_URL is not configured; proxy egress cannot be verified",
        )

    try:
        async with httpx.AsyncClient(
            proxy=settings.FIXIE_URL,
            trust_env=False,
            timeout=15.0,
        ) as client:
            response = await client.get("https://api.ipify.org?format=json")
            response.raise_for_status()
            address = response.json().get("ip")
            if not address:
                raise ValueError("IP response is missing an address")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Fixie outbound IP check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Fixie proxy outbound IP check failed",
        ) from None

    return {
        "proxy_configured": True,
        "outbound_ip": address,
        "status": "SUCCESS",
    }
