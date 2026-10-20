"""Regression tests for the Fixie diagnostic and outbound HTTP proxy wiring."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app

client = TestClient(app)


def test_outbound_route_exists_without_fixie(monkeypatch):
    monkeypatch.setattr(settings, "FIXIE_URL", "")
    response = client.get("/api/v1/diagnostics/outbound-ip")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_outbound_route_uses_fixie_without_disclosing_credentials(monkeypatch):
    proxy = "http://user:password@proxy.example:1234"
    monkeypatch.setattr(settings, "FIXIE_URL", proxy)

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ip": "192.0.2.1"}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs["proxy"] == proxy
            assert kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url == "https://api.ipify.org?format=json"
            return FakeResponse()

    with patch("backend.app.api.routes.diagnostics.httpx.AsyncClient", FakeAsyncClient):
        response = client.get("/api/v1/diagnostics/outbound-ip")
    assert response.status_code == 200
    assert response.json()["outbound_ip"] == "192.0.2.1"
    assert "password" not in response.text


def test_outbound_route_reports_proxy_failure(monkeypatch):
    monkeypatch.setattr(settings, "FIXIE_URL", "http://proxy.example:1234")

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            raise httpx.ConnectError("proxy connection failed")

    with patch("backend.app.api.routes.diagnostics.httpx.AsyncClient", FakeAsyncClient):
        response = client.get("/api/v1/diagnostics/outbound-ip")
    assert response.status_code == 502
    assert response.json()["detail"] == "Fixie proxy outbound IP check failed"
