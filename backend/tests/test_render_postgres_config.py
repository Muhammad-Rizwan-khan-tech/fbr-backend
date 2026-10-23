"""Render DATABASE_URL parsing tests: no live database connection or credentials needed."""
import pytest

from backend.app.core.db_url import normalize_database_url


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "postgres://username:p%40ss@dpg-example-a.oregon-postgres.render.com/fbrdb",
            "postgresql://username:p%40ss@dpg-example-a.oregon-postgres.render.com/fbrdb",
        ),
        (
            "postgresql://username:secret@dpg-example-a.oregon-postgres.render.com/fbrdb?sslmode=require",
            "postgresql://username:secret@dpg-example-a.oregon-postgres.render.com/fbrdb?sslmode=require",
        ),
        ("sqlite:///./test_ci.db", "sqlite:///./test_ci.db"),
        (' "postgresql://username:p%40ss@localhost:5432/appdb" ', "postgresql://username:p%40ss@localhost:5432/appdb"),
    ],
)
def test_accepts_and_preserves_render_database_url(source, expected):
    assert normalize_database_url(source) == expected


@pytest.mark.parametrize("source", [
    None, "", "dpg-dbdop6l9fdbs7384ugvg-a",
    "postgresql://", "postgresql://username:password@localhost",
    "postgresql://localhost/fbrdb", "mysql://root:password@localhost/private",
    "postgresql://user:password@@@",
])
def test_rejects_unusable_connection_values_safely(source):
    with pytest.raises(ValueError) as exc:
        normalize_database_url(source)
    assert "password" not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_invalid_url_does_not_leak_credentials():
    with pytest.raises(ValueError) as exc:
        normalize_database_url("postgresql://user:TOPSECRET@")
    assert "TOPSECRET" not in str(exc.value)
