from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_endpoint(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "components" in data
    # No storage in the unit-test environment: reported, not fatal for /health.
    assert data["components"]["storage"] in {"unreachable", "denied", "missing", "ok"}


async def test_health_reports_storage_status(client, monkeypatch):
    from app.routers import health as health_router
    from app.services.object_storage_service import BucketStatus

    class _Storage:
        async def check_bucket(self):
            return BucketStatus.OK

    monkeypatch.setattr(health_router, "get_object_storage_service", lambda: _Storage())
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["components"]["storage"] == "ok"
    assert resp.json()["status"] == "ok"

    ready = await client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


async def test_readiness_fails_when_storage_unusable(client, monkeypatch):
    from app.routers import health as health_router
    from app.services.object_storage_service import BucketStatus

    class _Storage:
        async def check_bucket(self):
            return BucketStatus.DENIED

    monkeypatch.setattr(health_router, "get_object_storage_service", lambda: _Storage())
    ready = await client.get("/api/v1/health/ready")
    assert ready.status_code == 503
    body = ready.json()
    assert body["status"] == "not_ready"
    assert body["components"]["storage"] == "denied"

    live = await client.get("/api/v1/health")
    assert live.status_code == 200
    assert live.json()["status"] == "degraded"


async def test_context_jsonld_endpoint(client):
    resp = await client.get("/api/v1/context.jsonld")
    assert resp.status_code == 200
    assert "@context" in resp.text


async def test_root_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "FairDataHive"
