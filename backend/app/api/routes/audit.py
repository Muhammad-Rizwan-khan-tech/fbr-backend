from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.tenant import Organization
from backend.app.models.audit import AuditLog
from backend.app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    action: Optional[str] = Query(None),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant.id)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    return query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
