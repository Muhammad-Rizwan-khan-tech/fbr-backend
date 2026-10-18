import enum
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TimestampMixin
from backend.app.core.crypto import encrypt_secret, decrypt_secret, mask_secret


class FBRConnectionStatus(str, enum.Enum):
    UNTESTED = "UNTESTED"
    HEALTHY = "HEALTHY"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class FBRCredential(Base, TimestampMixin):
    __tablename__ = "fbr_credentials"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    environment = Column(String(50), default="DEMO", nullable=False)  # DEMO | SANDBOX | PRODUCTION
    provider = Column(String(50), default="MOCK", nullable=False)  # MOCK | SANDBOX | LICENSED_INTEGRATOR | PRODUCTION
    fbr_pos_id = Column(String(100), nullable=True)
    base_url = Column(String(255), nullable=True)
    
    # Encrypted secrets (AES-256-GCM)
    encrypted_api_key = Column(Text, nullable=True)
    encrypted_client_id = Column(Text, nullable=True)
    encrypted_client_secret = Column(Text, nullable=True)
    encrypted_auth_token = Column(Text, nullable=True)
    encrypted_cert_passphrase = Column(Text, nullable=True)

    status = Column(String(50), default=FBRConnectionStatus.UNTESTED.value, nullable=False)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failed_at = Column(DateTime(timezone=True), nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)  # PRAL tokens valid for 5 years
    token_rotated_at = Column(DateTime(timezone=True), nullable=True)
    production_ready = Column(Boolean, default=False, nullable=False)
    sandbox_tested = Column(Boolean, default=False, nullable=False)
    last_error = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationship
    organization = relationship("Organization", backref="fbr_credential")

    def set_credentials(
        self,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        auth_token: Optional[str] = None,
        cert_passphrase: Optional[str] = None,
    ) -> None:
        """Encrypts and sets credential fields."""
        if api_key is not None:
            self.encrypted_api_key = encrypt_secret(api_key.strip()) if api_key else None
        if client_id is not None:
            self.encrypted_client_id = encrypt_secret(client_id.strip()) if client_id else None
        if client_secret is not None:
            self.encrypted_client_secret = encrypt_secret(client_secret.strip()) if client_secret else None
        if auth_token is not None:
            self.encrypted_auth_token = encrypt_secret(auth_token.strip()) if auth_token else None
        if cert_passphrase is not None:
            self.encrypted_cert_passphrase = encrypt_secret(cert_passphrase.strip()) if cert_passphrase else None

    def get_api_key(self) -> Optional[str]:
        return decrypt_secret(self.encrypted_api_key)

    def get_client_id(self) -> Optional[str]:
        return decrypt_secret(self.encrypted_client_id)

    def get_client_secret(self) -> Optional[str]:
        return decrypt_secret(self.encrypted_client_secret)

    def get_auth_token(self) -> Optional[str]:
        return decrypt_secret(self.encrypted_auth_token)

    def get_cert_passphrase(self) -> Optional[str]:
        return decrypt_secret(self.encrypted_cert_passphrase)

    def to_masked_dict(self) -> Dict[str, Any]:
        """Returns safe metadata and masked values for administrative review."""
        raw_key = self.get_api_key()
        raw_cid = self.get_client_id()
        raw_token = self.get_auth_token()
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "environment": self.environment,
            "provider": self.provider,
            "fbr_pos_id": self.fbr_pos_id,
            "base_url": self.base_url,
            "has_api_key": bool(raw_key),
            "masked_api_key": mask_secret(raw_key) if raw_key else "Not Configured",
            "has_client_id": bool(raw_cid),
            "masked_client_id": mask_secret(raw_cid) if raw_cid else "Not Configured",
            "has_client_secret": bool(self.encrypted_client_secret),
            "has_auth_token": bool(raw_token),
            "masked_auth_token": mask_secret(raw_token) if raw_token else "Not Configured",
            "has_cert_passphrase": bool(self.encrypted_cert_passphrase),
            "status": self.status,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_failed_at": self.last_failed_at.isoformat() if self.last_failed_at else None,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "token_rotated_at": self.token_rotated_at.isoformat() if self.token_rotated_at else None,
            "production_ready": self.production_ready,
            "sandbox_tested": self.sandbox_tested,
            "last_error": self.last_error,
            "is_active": self.is_active,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
