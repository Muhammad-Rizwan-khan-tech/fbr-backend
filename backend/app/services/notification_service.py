import logging
import smtplib
from email.message import EmailMessage
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.config import settings
from backend.app.models.notification import Notification, NotificationDelivery
from backend.app.models.user import User
from backend.app.models.base import now_utc

logger = logging.getLogger(__name__)


class NotificationService:
    """Manages in-app notifications and email dispatch records."""

    def create_notification(
        self,
        db: Session,
        tenant_id: str,
        user_id: str,
        event_type: str,
        title: str,
        message: str,
        severity: str = "INFO",
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Notification:
        notif = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif

    def notify_tenant_users(
        self,
        db: Session,
        tenant_id: str,
        event_type: str,
        title: str,
        message: str,
        severity: str = "INFO",
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> List[Notification]:
        users = db.query(User).filter(User.tenant_id == tenant_id, User.is_active == True).all()
        created = []
        for u in users:
            notif = Notification(
                tenant_id=tenant_id,
                user_id=u.id,
                event_type=event_type,
                severity=severity,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
            )
            db.add(notif)
            created.append(notif)
        if created:
            db.commit()
            for n in created:
                db.refresh(n)
        return created

    def list_notifications(
        self,
        db: Session,
        tenant_id: str,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Notification]:
        query = db.query(Notification).filter(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        )
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(desc(Notification.created_at)).limit(limit).all()

    def mark_as_read(
        self, db: Session, notification_id: str, tenant_id: str, user_id: str
    ) -> Optional[Notification]:
        notif = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
            )
            .first()
        )
        if notif and not notif.is_read:
            notif.is_read = True
            notif.read_at = now_utc()
            db.commit()
            db.refresh(notif)
        return notif

    def mark_all_as_read(self, db: Session, tenant_id: str, user_id: str) -> int:
        now = now_utc()
        updated = (
            db.query(Notification)
            .filter(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
            .update({"is_read": True, "read_at": now})
        )
        db.commit()
        return updated

    def send_email_notification(
        self,
        db: Session,
        tenant_id: str,
        recipient: str,
        subject: str,
        body: str,
        event_type: str = "SYSTEM",
        correlation_id: Optional[str] = None,
    ) -> NotificationDelivery:
        delivery = NotificationDelivery(
            tenant_id=tenant_id,
            event_type=event_type,
            channel="EMAIL",
            recipient=recipient,
            subject=subject,
            status="PENDING",
            correlation_id=correlation_id,
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        if not settings.SMTP_HOST:
            logger.info(
                f"[MOCK EMAIL] To: {recipient} | Subject: {subject} | SMTP not configured, delivery marked SKIPPED"
            )
            delivery.status = "SKIPPED"
            delivery.last_error = "SMTP host not configured"
            db.commit()
            return delivery

        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = recipient

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

            delivery.status = "SENT"
            delivery.sent_at = now_utc()
            delivery.attempt_count += 1
            db.commit()
        except Exception as exc:
            logger.warning(f"Failed to send email to {recipient}: {exc}")
            delivery.status = "FAILED"
            delivery.last_error = str(exc)
            delivery.attempt_count += 1
            db.commit()

        return delivery


notification_service = NotificationService()
