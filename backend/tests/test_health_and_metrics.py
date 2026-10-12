from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "components" in data
    assert "database" in data["components"]
    assert data["components"]["database"]["status"] == "UP"
    assert "storage" in data["components"]
    assert data["components"]["storage"]["status"] == "UP"


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    content = response.text
    assert "# HELP" in content
    assert "http_requests_total" in content
    assert "fbr_submissions_total" in content
