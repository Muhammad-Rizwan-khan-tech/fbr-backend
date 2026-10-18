from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

# Engine configuration with sqlite threading support
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_schema_columns(target_engine=None) -> None:
    """Idempotently creates missing tables and adds additive PRAL v1.12 columns
    to existing SQLite/Postgres tables without losing data.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    try:
        inspector = inspect(eng)
        existing_tables = set(inspector.get_table_names())
        migrations = []

        if "users" in existing_tables:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "username" not in user_cols:
                migrations.append("ALTER TABLE users ADD COLUMN username VARCHAR(100)")

        if "invoices" in existing_tables:
            inv_cols = {c["name"] for c in inspector.get_columns("invoices")}
            if "scenario_id" not in inv_cols:
                migrations.append("ALTER TABLE invoices ADD COLUMN scenario_id VARCHAR(20)")

        if "invoice_items" in existing_tables:
            itm_cols = {c["name"] for c in inspector.get_columns("invoice_items")}
            additive_cols = [
                ("rate_desc", "VARCHAR(120)"),
                ("fixed_notified_value_or_retail_price", "NUMERIC(14, 2) NOT NULL DEFAULT 0.00"),
                ("sales_tax_withheld_at_source", "NUMERIC(14, 2) NOT NULL DEFAULT 0.00"),
                ("extra_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0.00"),
                ("further_tax", "NUMERIC(14, 2) NOT NULL DEFAULT 0.00"),
                ("fed_payable", "NUMERIC(14, 2) NOT NULL DEFAULT 0.00"),
                ("sro_item_serial_no", "VARCHAR(100)"),
            ]
            for col_name, col_type in additive_cols:
                if col_name not in itm_cols:
                    migrations.append(f"ALTER TABLE invoice_items ADD COLUMN {col_name} {col_type}")

        if migrations:
            with eng.begin() as conn:
                for stmt in migrations:
                    conn.execute(text(stmt))
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
