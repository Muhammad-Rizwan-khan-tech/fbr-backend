import json
from typing import Optional, Any
from sqlalchemy.orm import Session
from backend.app.models.audit import AuditLog


class AuditService:
    @staticmethod
    def log(
        db: Session,
        tenant_id: str,
        action: str,
        entity: str,
        entity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        before_state: Optional[Any] = None,
        after_state: Optional[Any] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> AuditLog:
        before_str = json.dumps(before_state, default=str) if before_state is not None else None
        after_str = json.dumps(after_state, default=str) if after_state is not None else None

        audit_entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_email=user_email,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before_state=before_str,
            after_state=after_str,
            ip_address=ip_address,
            correlation_id=correlation_id
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry
