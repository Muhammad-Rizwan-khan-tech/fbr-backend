from sqlalchemy import Column, String, DateTime, Text
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, now_utc


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    
    action = Column(String(100), nullable=False, index=True) # e.g. "INVOICE_CREATE", "FBR_SUBMIT", "SETTINGS_UPDATE"
    entity = Column(String(100), nullable=False, index=True) # e.g. "Invoice", "Customer", "Taxpayer"
    entity_id = Column(String(36), nullable=True, index=True)
    
    timestamp = Column(DateTime(timezone=True), default=now_utc, nullable=False, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    before_state = Column(Text, nullable=True)
    after_state = Column(Text, nullable=True)
    correlation_id = Column(String(50), nullable=True)


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=False, index=True)
    provider_name = Column(String(100), default="PRAL / Licensed Integrator", nullable=False)
    mode = Column(String(50), default="DEMO", nullable=False) # DEMO, SANDBOX, PRODUCTION
    api_base_url = Column(String(255), nullable=True)
    pos_id = Column(String(100), nullable=True)
    client_id = Column(String(100), nullable=True)
    client_secret_masked = Column(String(100), nullable=True)
    is_active = Column(String(10), default="true", nullable=False)
