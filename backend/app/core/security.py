import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from backend.app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(
    subject: Union[str, Any],
    tenant_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "role": str(role),
        "iat": datetime.now(timezone.utc)
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------------------
# Developer API Key cryptography
# ---------------------------------------------------------------------------------
import hashlib
import hmac
import secrets
from typing import Tuple


def generate_api_key(environment: str = "TEST") -> Tuple[str, str, str]:
    """Generate an API key with standard format and SHA-256 hash for storage.

    Returns:
        (raw_key, key_prefix, hashed_key)
        - raw_key: Returned to caller ONCE (e.g. "fbr_test_3a8b...").
        - key_prefix: Non-sensitive preview (e.g. "fbr_test_3a8b1234").
        - hashed_key: SHA-256 hex digest stored in DB.
    """
    env_tag = "live" if environment.upper() == "LIVE" else "test"
    random_part = secrets.token_hex(24)  # 48 hex chars
    raw_key = f"fbr_{env_tag}_{random_part}"
    key_prefix = raw_key[:16]
    hashed_key = hash_api_key(raw_key)
    return raw_key, key_prefix, hashed_key


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time verification of raw API key against stored SHA-256 hash."""
    computed_hash = hash_api_key(raw_key)
    return hmac.compare_digest(computed_hash, stored_hash)


# ---------------------------------------------------------------------------------
# Webhook Signature cryptography
# ---------------------------------------------------------------------------------
def generate_webhook_secret() -> str:
    """Generate an HMAC signing secret for a webhook endpoint."""
    return f"whsec_{secrets.token_hex(24)}"


def sign_webhook_payload(secret: str, payload_bytes: bytes, timestamp: int) -> str:
    """Compute HMAC-SHA256 signature for a webhook delivery payload.

    Signature format follows standard v1 signature scheme:
    HMAC_SHA256(secret, "{timestamp}.{payload}")
    """
    to_sign = f"{timestamp}.".encode("utf-8") + payload_bytes
    signature = hmac.new(
        secret.encode("utf-8"),
        to_sign,
        hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def verify_webhook_signature(
    secret: str,
    payload_bytes: bytes,
    header_signature: str,
    tolerance_seconds: int = 300
) -> bool:
    """Verify that a webhook signature matches and is not stale."""
    try:
        parts = dict(item.split("=", 1) for item in header_signature.split(","))
        timestamp = int(parts.get("t", 0))
        received_sig = parts.get("v1", "")
        if not timestamp or not received_sig:
            return False

        # Tolerance check (replay attack protection)
        current_time = int(datetime.now(timezone.utc).timestamp())
        if abs(current_time - timestamp) > tolerance_seconds:
            return False

        expected_sig = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(received_sig, expected_sig)
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """Validate password complexity requirements."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    has_digit = any(c.isdigit() for c in password)
    has_letter = any(c.isalpha() for c in password)
    if not (has_digit and has_letter):
        return False, "Password must contain both letters and numbers."
    return True, None

