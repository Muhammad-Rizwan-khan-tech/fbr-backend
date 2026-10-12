"""Structured (JSON) logging with automatic context and secret redaction."""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from backend.app.core import context

SENSITIVE_KEYS = re.compile(
    r"(password|passwd|secret|token|authorization|api[_-]?key|private[_-]?key|credential|cookie)",
    re.IGNORECASE,
)
REDACTED = "***REDACTED***"

# Attributes that exist on every LogRecord; anything else passed via ``extra`` is
# treated as a structured field.
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {"message", "asctime"}


def redact(value: Any, _key: str = "") -> Any:
    """Recursively mask values whose key looks sensitive."""
    if _key and SENSITIVE_KEYS.search(_key):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, _key) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, environment: str):
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "environment": self.environment,
            "logger": record.name,
            "event": getattr(record, "event", None) or record.getMessage(),
        }
        # Context (request_id, correlation_id, tenant_id, user_id, ...)
        for key, value in context.snapshot().items():
            if value:
                payload[key] = value
        # Explicit structured fields passed through ``extra=``
        for key, value in record.__dict__.items():
            if key in _RESERVED or key == "event" or key.startswith("_"):
                continue
            payload[key] = redact(value, key)
        if record.exc_info:
            payload["error"] = payload.get("error") or f"{record.exc_info[0].__name__}: {record.exc_info[1]}"
            payload["exc_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging(service: str, environment: str, level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service=service, environment=environment))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Uvicorn's access log duplicates our request log middleware.
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("botocore", "boto3", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def setup_logging(level: str = "INFO") -> None:
    from backend.app.core.config import settings
    configure_logging(
        service=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        level=level or settings.LOG_LEVEL,
    )



def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Emit a structured event: ``log_event(log, "fbr.submission.accepted", job_id=..., duration=...)``."""
    logger.log(level, event, extra={"event": event, **fields})
