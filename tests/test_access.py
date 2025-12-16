from __future__ import annotations

import pytest

from tests.test_resources import VALID_PAYLOAD

pytestmark = pytest.mark.asyncio


PRIVATE_PAYLOAD = {
    **VALID_PAYLOAD,
    "is_private": True,
    "access_rights": [],
}


async def _publish(client, payload):
    create = await client.post("/api/v1/resources", json=payload)
    body = create.json()
    pub = await client.post(f"/api/v1/resources/{body['id']}/publish")
    assert pub.status_code == 200, pub.text
    return body["id"]


async def test_access_status_for_public_resource(client):
    version_id = await _publish(client, VALID_PAYLOAD)
    resp = await client.get(f"/api/v1/resources/{version_id}/access")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_private"] is False
    assert data["has_access"] is True


async def test_owner_has_access_to_private_resource(client):
    version_id = await _publish(client, PRIVATE_PAYLOAD)
    resp = await client.get(f"/api/v1/resources/{version_id}/access")
    data = resp.json()
    assert data["is_owner"] is True
    assert data["has_access"] is True


async def test_other_user_cannot_request_own_resource(client):
    version_id = await _publish(client, PRIVATE_PAYLOAD)
    # the test user is the owner; self-request returns 409
    resp = await client.post(
        "/api/v1/access-requests",
        json={"resource_version_id": version_id, "message": "please"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "self_request"


async def test_public_resource_blocks_access_request(client):
    version_id = await _publish(client, VALID_PAYLOAD)
    resp = await client.post(
        "/api/v1/access-requests",
        json={"resource_version_id": version_id},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "resource_public"


async def test_access_request_workflow(client):
    """End-to-end workflow with two different users."""

    from app.main import app
    from app.core.auth import CurrentUser

    requester = CurrentUser(
        sub="requester-1",
        preferred_username="alice",
        email="alice@example.org",
        name="Alice",
    )

    version_id = await _publish(client, PRIVATE_PAYLOAD)

    app.state._auth_override = lambda req, creds: requester
    create_req = await client.post(
        "/api/v1/access-requests",
        json={"resource_version_id": version_id, "message": "please"},
    )
    assert create_req.status_code == 201, create_req.text
    req_id = create_req.json()["id"]

    # Owner views incoming requests
    from app.core.auth import CurrentUser as CU
    owner = CU(sub="user-test-1", name="Test User")
    app.state._auth_override = lambda req, creds: owner

    incoming = await client.get("/api/v1/access-requests/incoming")
    assert incoming.status_code == 200
    assert any(r["id"] == req_id for r in incoming.json())

    accept = await client.post(f"/api/v1/access-requests/{req_id}/accept")
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    # Requester now has access
    app.state._auth_override = lambda req, creds: requester
    status = await client.get(f"/api/v1/resources/{version_id}/access")
    assert status.status_code == 200
    assert status.json()["has_access"] is True


async def test_tombstone_returns_410_with_metadata(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    body = create.json()
    await client.post(f"/api/v1/resources/{body['id']}/publish")

    deleted = await client.delete(f"/api/v1/resources/{body['base_resource_id']}")
    assert deleted.status_code == 204

    resp = await client.get(f"/api/v1/resources/{body['id']}")
    assert resp.status_code == 410
    err = resp.json()
    assert err["error"] == "resource_deleted"
    assert err["details"]["tombstone"]["data_deleted"] is True
