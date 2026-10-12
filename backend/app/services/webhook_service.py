import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models.webhook import WebhookEndpoint
from backend.app.services.queue_service import queue_service

logger = logging.getLogger(__name__)


class WebhookService:
    @staticmethod
    def dispatch_event(
        db: Session,
        tenant_id: str,
        event_type: str,
        payload_data: Dict[str, Any]
    ) -> int:
        """Finds all active webhook endpoints matching the event and enqueues deliveries.
        
        Returns the number of endpoints queued.
        """
        endpoints = db.query(WebhookEndpoint).filter(
            WebhookEndpoint.tenant_id == tenant_id,
            WebhookEndpoint.is_active == True
        ).all()

        if not endpoints:
            return 0

        queued_count = 0
        envelope = {
            "event": event_type,
            "tenant_id": tenant_id,
            "data": payload_data,
        }
        payload_str = json.dumps(envelope, default=str)

        for ep in endpoints:
            subscribed = [e.strip() for e in ep.events.split(",") if e.strip()]
            if "*" in subscribed or event_type in subscribed:
                try:
                    queue_service.enqueue_task(
                        "backend.app.workers.tasks.dispatch_webhook_task",
                        args=[ep.id, tenant_id, event_type, payload_str, 1, 3],
                        queue_name="notifications"
                    )
                    queued_count += 1
                except Exception as exc:
                    logger.error(f"Failed to enqueue webhook delivery for endpoint {ep.id}: {exc}")

        return queued_count


webhook_service = WebhookService()
