from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, UniqueConstraint, Index
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TimestampMixin, now_utc


class FBRReferenceCatalog(Base, TimestampMixin):
    """Stores cached FBR/PRAL DI API v1.12 reference datasets with explicit provenance,
    request parameter fingerprinting, and TTL freshness metadata.
    """
    __tablename__ = "fbr_reference_catalogs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=True, index=True)  # NULL for global dictionaries, set for tenant-scoped checks
    catalog_key = Column(String(100), nullable=False, index=True)
    request_fingerprint = Column(String(128), nullable=False, index=True)
    source = Column(String(50), nullable=False, default="DEMO_FIXTURE")  # PRAL_LIVE | OFFICIAL_IMPORT | DEMO_FIXTURE
    source_version = Column(String(50), nullable=False, default="1.12")
    payload = Column(Text, nullable=False)  # JSON serialized list/object
    record_count = Column(Integer, nullable=False, default=0)
    fetched_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    effective_date = Column(String(30), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")  # ACTIVE | STALE | FAILED
    official_live_verified = Column(Boolean, nullable=False, default=False)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "catalog_key",
            "request_fingerprint",
            name="uq_fbr_ref_catalog_tenant_key_fp",
        ),
        Index("ix_fbr_ref_catalog_lookup", "catalog_key", "request_fingerprint"),
    )


class FBRReferenceSyncRun(Base, TimestampMixin):
    """Audit trail of reference catalog synchronization attempts and outcomes."""
    __tablename__ = "fbr_reference_sync_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=True, index=True)
    catalog_key = Column(String(100), nullable=False, index=True)
    request_fingerprint = Column(String(128), nullable=True)
    provider_mode = Column(String(50), nullable=False, default="DEMO_FIXTURE")
    started_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    outcome = Column(String(50), nullable=False)  # SUCCESS | FAILED | SKIPPED_NO_CREDENTIALS | FALLBACK_FIXTURE
    record_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(50), nullable=True)
    error_summary = Column(Text, nullable=True)
    triggered_by = Column(String(100), nullable=True)
