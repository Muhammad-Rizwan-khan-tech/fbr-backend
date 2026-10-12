import os
import base64
import hashlib
import secrets
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.app.core.config import settings


def get_encryption_key() -> bytes:
    """Derives or returns a 32-byte AES-256 key from settings."""
    custom_key = getattr(settings, "FBR_CREDENTIAL_ENCRYPTION_KEY", "")
    if custom_key and len(custom_key.strip()) >= 32:
        return hashlib.sha256(custom_key.strip().encode("utf-8")).digest()
    
    # Fallback to deriving from application SECRET_KEY
    salt = b"fbr-invoice-cloud-aes-gcm-key-salt"
    return hashlib.pbkdf2_hmac("sha256", settings.SECRET_KEY.encode("utf-8"), salt, 100_000, dklen=32)


def encrypt_secret(plaintext: Optional[str]) -> Optional[str]:
    """Encrypts a plaintext string using AES-256-GCM with a random 12-byte nonce.
    
    Returns base64 encoded string: nonce (12 bytes) + ciphertext + tag (16 bytes).
    """
    if not plaintext:
        return None
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce standard for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode("utf-8")


def decrypt_secret(encrypted_b64: Optional[str]) -> Optional[str]:
    """Decrypts a base64 encoded AES-256-GCM ciphertext payload."""
    if not encrypted_b64:
        return None
    try:
        key = get_encryption_key()
        aesgcm = AESGCM(key)
        payload = base64.b64decode(encrypted_b64.encode("utf-8"))
        if len(payload) < 28:  # 12 nonce + 16 tag minimum
            return None
        nonce = payload[:12]
        ciphertext = payload[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception:
        return None


def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Masks sensitive credentials for administrative overview (e.g. 'fbr_****7890')."""
    if not secret:
        return "Not Configured"
    cleaned = secret.strip()
    if len(cleaned) <= visible_chars * 2:
        return "********"
    return f"{cleaned[:visible_chars]}****{cleaned[-visible_chars:]}"


def generate_activation_secret() -> str:
    """Generates a secure, human-friendly 20-character desktop activation secret.
    
    Format: ACT-XXXX-XXXX-XXXX-XXXX (using unambiguous alphanumeric characters)
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Omits 0/O, 1/I to prevent user typos
    chunks = []
    for _ in range(4):
        chunk = "".join(secrets.choice(alphabet) for _ in range(4))
        chunks.append(chunk)
    return f"ACT-{'-'.join(chunks)}"


def hash_activation_secret(secret: str) -> str:
    """Normalizes and hashes an activation secret with SHA-256."""
    normalized = secret.strip().upper().replace(" ", "").replace("-", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_device_token() -> str:
    """Generates a secure random 32-byte hex string for device authentication."""
    return secrets.token_hex(32)
