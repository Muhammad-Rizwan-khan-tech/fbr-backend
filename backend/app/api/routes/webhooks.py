from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.tenant import Organization
from backend.app.models.webhook import WebhookEndpoint, WebhookDelivery
from backend.app.core.security import generate_webhook_secret
from backend.app.schemas.webhook import (
    WebhookEndpointCreate, WebhookEndpointResponse, WebhookDeliveryResponse
)
from backend.app.services.webhook_service import webhook_service
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/endpoints", response_model=WebhookEndpointResponse, status_code=status.HTTP_201_CREATED)
def register_webhook_endpoint(
    data: WebhookEndpointCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """Register a destination HTTPS endpoint to receive asynchronous FBR invoice and compliance events."""
    if not (data.url.startswith("https://") or data.url.startswith("http://localhost")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Webhook URL must use secure HTTPS protocol (or http://localhost for local testing)."
        )

    secret = generate_webhook_secret()
    events_str = ",".join(data.events) if data.events else "*"

    endpoint = WebhookEndpoint(
        tenant_id=tenant.id,
        url=data.url,
        secret=secret,
        description=data.description,
        events=events_str,
        is_active=True,
        created_by=current_user.id
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="REGISTER_WEBHOOK_ENDPOINT",
        entity="WebhookEndpoint",
        entity_id=endpoint.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={"url": endpoint.url, "events": events_str}
    )

    return endpoint


@router.get("/endpoints", response_model=List[WebhookEndpointResponse])
def list_webhook_endpoints(
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """List all registered webhook endpoints for the current organization."""
    return db.query(WebhookEndpoint).filter(
        WebhookEndpoint.tenant_id == tenant.id
    ).order_by(WebhookEndpoint.created_at.desc()).all()


@router.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook_endpoint(
    endpoint_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """Delete a webhook endpoint and remove its delivery configurations."""
    endpoint = db.query(WebhookEndpoint).filter(
        WebhookEndpoint.id == endpoint_id,
        WebhookEndpoint.tenant_id == tenant.id
    ).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    db.delete(endpoint)
    db.commit()

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="DELETE_WEBHOOK_ENDPOINT",
        entity="WebhookEndpoint",
        entity_id=endpoint_id,
        user_id=current_user.id,
        user_email=current_user.email
    )
    return None


@router.post("/endpoints/{endpoint_id}/test")
def test_webhook_endpoint(
    endpoint_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """Send an immediate test event ping to verify connectivity and signature validation."""
    endpoint = db.query(WebhookEndpoint).filter(
        WebhookEndpoint.id == endpoint_id,
        WebhookEndpoint.tenant_id == tenant.id
    ).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    test_payload = {
        "event": "endpoint.test",
        "message": "FBR Invoice Cloud test webhook ping",
        "endpoint_id": endpoint.id,
        "tenant_id": tenant.id,
    }

    count = webhook_service.dispatch_event(
        db=db,
        tenant_id=tenant.id,
        event_type="endpoint.test",
        payload_data=test_payload
    )

    return {
        "success": True,
        "message": f"Test event queued for transmission to {endpoint.url}",
        "endpoint_id": endpoint.id,
        "queued": count
    }


@router.get("/deliveries", response_model=List[WebhookDeliveryResponse])
def list_webhook_deliveries(
    endpoint_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.SUPER_ADMIN.value)),
    db: Session = Depends(get_db)
):
    """Inspect recent webhook delivery execution logs, HTTP response codes, and errors."""
    query = db.query(WebhookDelivery).filter(WebhookDelivery.tenant_id == tenant.id)
    if endpoint_id:
        query = query.filter(WebhookDelivery.endpoint_id == endpoint_id)
    if status:
        query = query.filter(WebhookDelivery.status == status.upper())

    return query.order_by(WebhookDelivery.created_at.desc()).limit(limit).all()
