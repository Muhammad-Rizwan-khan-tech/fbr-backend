"""Normalize SQLAlchemy database URLs without logging database credentials.

Render supplies DATABASE_URL as a complete URI. The dpg-* identifier alone is
not a usable DATABASE_URL and must never be hardcoded as a credential.
"""
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def normalize_database_url(value: str | None) -> str:
    raw = (value or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("DATABASE_URL is empty; set the full database connection URL in Render")
    if raw.startswith("dpg-") or "://" not in raw:
        raise ValueError(
            "DATABASE_URL requires the full Render Internal Database URL; "
            "a dpg-* host or database identifier alone is not enough"
        )
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    try:
        parsed = make_url(raw)
    except (ArgumentError, ValueError, TypeError, AttributeError):
        raise ValueError("DATABASE_URL is not a valid SQLAlchemy database URL") from None

    dialect = parsed.get_backend_name()
    if dialect not in ("postgresql", "sqlite"):
        raise ValueError("DATABASE_URL must use PostgreSQL or SQLite")
    if dialect == "postgresql" and (
        not parsed.host or not parsed.database or not parsed.username
    ):
        raise ValueError(
            "PostgreSQL DATABASE_URL must include username, host, and database name"
        )
    # Return the original credential-bearing URL unchanged (apart from legacy
    # scheme normalization); never log it or use SQLAlchemy's redacted str(url).
    return raw
