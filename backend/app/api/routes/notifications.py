from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.schemas.notification import NotificationResponse, NotificationUnreadCountResponse
from backend.app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationResponse])
def get_user_notifications(
    unread_only: bool = Query(False, description="Filter to only unread notifications"),
    limit: int = Query(50, ge=1, le=100),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve notifications for the authenticated user and tenant."""
    return notification_service.list_notifications(
        db=db,
        tenant_id=tenant.id,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_count(
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get total number of unread notifications for current user."""
    items = notification_service.list_notifications(
        db=db,
        tenant_id=tenant.id,
        user_id=current_user.id,
        unread_only=True,
        limit=500,
    )
    return NotificationUnreadCountResponse(unread_count=len(items))


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a specific notification as read."""
    notif = notification_service.mark_as_read(
        db=db,
        notification_id=notification_id,
        tenant_id=tenant.id,
        user_id=current_user.id,
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif


@router.post("/read-all")
def mark_all_notifications_read(
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all unread notifications for current user as read."""
    count = notification_service.mark_all_as_read(
        db=db,
        tenant_id=tenant.id,
        user_id=current_user.id,
    )
    return {"message": "All notifications marked as read", "updated_count": count}
