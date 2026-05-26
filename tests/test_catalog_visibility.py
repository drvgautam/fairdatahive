from __future__ import annotations

import pytest

from tests.test_resources import VALID_PAYLOAD

pytestmark = pytest.mark.asyncio


async def test_private_published_excluded_from_public_discovery(client):
    payload = {
        **VALID_PAYLOAD,
        "is_private": True,
        "access_rights": ["user-test-1"],
    }
    create = await client.post("/api/v1/resources", json=payload)
    assert create.status_code == 201, create.text
    version_id = create.json()["id"]

    pub = await client.post(f"/api/v1/resources/{version_id}/publish")
    assert pub.status_code == 200, pub.text

    listing = await client.get("/api/v1/resources")
    assert version_id not in [v["id"] for v in listing.json()["items"]]

    catalog = await client.get("/api/v1/catalog")
    assert version_id not in [i["id"] for i in catalog.json()["items"]]

    search = await client.get("/api/v1/search")
    assert version_id not in [
        h["resource"]["id"] for h in search.json()["results"]
    ]
