from __future__ import annotations

import pytest

from tests.test_resources import VALID_PAYLOAD

pytestmark = pytest.mark.asyncio


async def test_stats_owner_only(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    body = create.json()
    await client.post(f"/api/v1/resources/{body['id']}/publish")

    resp = await client.get(f"/api/v1/resources/{body['base_resource_id']}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_downloads" in data
    assert data["total_downloads"] == 0


async def test_stats_forbidden_for_other_user(client):
    from app.core.auth import CurrentUser
    from app.main import app

    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    base = create.json()["base_resource_id"]
    await client.post(f"/api/v1/resources/{create.json()['id']}/publish")

    intruder = CurrentUser(sub="someone-else")
    app.state._auth_override = lambda req, creds: intruder

    resp = await client.get(f"/api/v1/resources/{base}/stats")
    assert resp.status_code == 403


async def test_notifications_endpoint(client):
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
