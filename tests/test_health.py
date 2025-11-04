from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_endpoint(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "components" in data


async def test_context_jsonld_endpoint(client):
    resp = await client.get("/api/v1/context.jsonld")
    assert resp.status_code == 200
    assert "@context" in resp.text


async def test_root_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "FairDataHive"
