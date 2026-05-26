from __future__ import annotations

import pytest

from tests.test_resources import VALID_PAYLOAD

pytestmark = pytest.mark.asyncio


async def _create_private_published(client):  # owner-authenticated client
    payload = {
        **VALID_PAYLOAD,
        "is_private": True,
        "access_rights": ["user-test-1"],
    }
    create = await client.post("/api/v1/resources", json=payload)
    version_id = create.json()["id"]
    await client.post(f"/api/v1/resources/{version_id}/publish")
    return version_id, create.json()["base_resource_id"]


async def test_anonymous_cannot_read_private_published_version(client):
    from app.main import app

    version_id, _ = await _create_private_published(client)
    app.state._auth_override = None
    resp = await client.get(f"/api/v1/resources/{version_id}")
    assert resp.status_code == 404


async def test_anonymous_cannot_read_draft(client):
    from app.main import app

    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    assert create.status_code == 201, create.text
    version_id = create.json()["id"]
    app.state._auth_override = None
    resp = await client.get(f"/api/v1/resources/{version_id}")
    assert resp.status_code == 404


async def test_owner_can_read_private_published(client):
    version_id, _ = await _create_private_published(client)
    resp = await client.get(f"/api/v1/resources/{version_id}")
    assert resp.status_code == 200
    assert resp.json()["is_private"] is True
