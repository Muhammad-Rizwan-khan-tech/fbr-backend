"""One credential authentication status for admin and desktop endpoints."""
from datetime import datetime, timezone


def connection_status(credential, mode):
    if (not credential or not credential.is_active or
            not (credential.encrypted_auth_token or credential.encrypted_api_key)):
        return "NOT_CONFIGURED"
    if str(mode).upper() not in ("SANDBOX", "PRODUCTION"):
        return "CONFIGURED_NOT_VERIFIED"
    if str(credential.environment).upper() != str(mode).upper():
        return "CONFIGURED_NOT_VERIFIED"
    expires = credential.token_expires_at
    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return "AUTHENTICATION_FAILED"
    if credential.status in ("VERIFIED", "HEALTHY") and credential.last_success_at:
        return "VERIFIED"
    if credential.status == "AUTH_FAILED":
        return "AUTHENTICATION_FAILED"
    if credential.status == "CONNECTION_UNAVAILABLE":
        return "CONNECTION_UNAVAILABLE"
    return "CONFIGURED_NOT_VERIFIED"


def connection_label(credential, mode):
    return {"NOT_CONFIGURED": "Not Configured", "VERIFIED": "Verified",
            "AUTHENTICATION_FAILED": "Authentication Failed",
            "CONNECTION_UNAVAILABLE": "Connection Unavailable",
            "CONFIGURED_NOT_VERIFIED": "Configured — Not Verified"}[connection_status(credential, mode)]
