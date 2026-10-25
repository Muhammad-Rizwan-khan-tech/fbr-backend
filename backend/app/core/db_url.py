"""Validate database URLs without exposing credentials."""
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def normalize_database_url(value: str | None) -> str:
    raw = (value or "").strip().strip('"').strip("'")
    if not raw or "://" not in raw:
        raise ValueError("DATABASE_URL must be a complete PostgreSQL or SQLite URL")
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    try:
        parsed = make_url(raw)
    except (ArgumentError, ValueError, TypeError, AttributeError):
        raise ValueError("DATABASE_URL is invalid") from None
    if parsed.get_backend_name() not in ("postgresql", "sqlite"):
        raise ValueError("DATABASE_URL must use PostgreSQL or SQLite")
    if parsed.get_backend_name() == "postgresql":
        if not parsed.host or not parsed.username or not parsed.database:
            raise ValueError("PostgreSQL URL requires username, host and database")
        if parsed.drivername == "postgresql":
            raw = "postgresql+psycopg://" + raw.split("://", 1)[1]
    return raw
