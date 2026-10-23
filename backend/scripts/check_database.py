"""Read-only Render PostgreSQL diagnostic.

Run from the deployed backend container:
    python -m backend.scripts.check_database
Prints no DATABASE_URL, usernames, passwords or customer data.
"""
from sqlalchemy import inspect, text
from backend.app.core.database import engine


def main():
    print("Database dialect:", engine.dialect.name)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
        print("Connection: OK")
        print("Schema tables:", len(tables))
        print("organizations:", "PRESENT" if "organizations" in tables else "MISSING")
        print("invoices:", "PRESENT" if "invoices" in tables else "MISSING")
        print("fbr_credentials:", "PRESENT" if "fbr_credentials" in tables else "MISSING")
        if "organizations" not in tables:
            print("ACTION: Database is connected but application schema is not initialized.")
    except Exception as error:
        # Never print raw DBAPI exception text: it may contain connection details.
        print("Connection: FAILED")
        print("Error type:", type(error).__name__)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
