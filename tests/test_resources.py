from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


VALID_PAYLOAD = {
    "scope": "public",
    "title": "EIS measurements on AA2024 alloy",
    "description": (
        "Electrochemical impedance spectra collected at OCP for AA2024 "
        "samples exposed to 0.5M NaCl solution."
    ),
    "keywords": ["electrochemistry", "impedance"],
    "theme": "Electrochemistry",
    "language": "en",
    "license_id": "CC-BY-4.0",
    "provenance": "Collected at the EUSC group using Gamry FRA on June 1, 2025.",
    "rights_statement": "Cite this dataset when reusing.",
    "datasets": [
        {
            "distributions": [
                {
                    "dist_type": "upload",
                    "title": "eis-data.csv",
                    "upload_token": "public/draft-1/eis-data.csv",
                    "media_type": "text/csv",
                    "checksum_sha256": "a" * 64,
                    "byte_size": 12345,
                }
            ]
        }
    ],
}


async def test_create_resource_returns_draft(client):
    resp = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["state"] == "draft"
    assert body["title"] == VALID_PAYLOAD["title"]
    assert body["base_resource_id"].startswith("resource-")
    assert body["id"].startswith(body["base_resource_id"] + "-v-")
    assert len(body["datasets"]) == 1
    assert len(body["datasets"][0]["distributions"]) == 1


async def test_create_resource_rejects_short_description(client):
    bad = dict(VALID_PAYLOAD)
    bad["description"] = "too short"
    resp = await client.post("/api/v1/resources", json=bad)
    assert resp.status_code == 422


async def test_create_resource_rejects_single_keyword(client):
    bad = dict(VALID_PAYLOAD)
    bad["keywords"] = ["only-one"]
    resp = await client.post("/api/v1/resources", json=bad)
    assert resp.status_code == 422


async def test_create_resource_rejects_empty_upload_token(client):
    payload = {
        **VALID_PAYLOAD,
        "datasets": [
            {
                "distributions": [
                    {
                        "dist_type": "upload",
                        "title": "archive.zip",
                        "upload_token": "",
                        "byte_size": 100,
                    }
                ]
            }
        ],
    }
    resp = await client.post("/api/v1/resources", json=payload)
    assert resp.status_code == 422
    assert "upload_token" in resp.text.lower()


async def test_create_resource_accepts_extracted_zip_members(client):
    payload = {
        **VALID_PAYLOAD,
        "datasets": [
            {
                "distributions": [
                    {
                        "dist_type": "upload",
                        "title": "a.csv",
                        "upload_token": "public/draft-1/a.csv",
                        "media_type": "text/csv",
                        "checksum_sha256": "a" * 64,
                        "byte_size": 10,
                    },
                    {
                        "dist_type": "upload",
                        "title": "b.csv",
                        "upload_token": "public/draft-1/b.csv",
                        "media_type": "text/csv",
                        "checksum_sha256": "b" * 64,
                        "byte_size": 20,
                    },
                ]
            }
        ],
    }
    resp = await client.post("/api/v1/resources", json=payload)
    assert resp.status_code == 201, resp.text
    dists = resp.json()["datasets"][0]["distributions"]
    assert len(dists) == 2


async def test_patch_draft_updates_fields(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    version_id = create.json()["id"]

    patch = await client.patch(
        f"/api/v1/resources/{version_id}",
        json={"title": "Updated title", "keywords": ["new", "tags"]},
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["title"] == "Updated title"
    assert "new" in body["keywords"]


async def test_publish_requires_license(client):
    payload = {**VALID_PAYLOAD, "license_id": None}
    create = await client.post("/api/v1/resources", json=payload)
    version_id = create.json()["id"]

    pub = await client.post(f"/api/v1/resources/{version_id}/publish")
    assert pub.status_code == 422, pub.text
    body = pub.json()
    assert body["error"] == "publish_guard_failed"
    failed_checks = [d["check"] for d in body["details"]]
    assert "license" in failed_checks


async def test_publish_requires_distribution(client):
    payload = {**VALID_PAYLOAD, "datasets": []}
    create = await client.post("/api/v1/resources", json=payload)
    version_id = create.json()["id"]

    pub = await client.post(f"/api/v1/resources/{version_id}/publish")
    assert pub.status_code == 422
    failed_checks = [d["check"] for d in pub.json()["details"]]
    assert "distribution" in failed_checks


async def test_full_publish_success(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    version_id = create.json()["id"]

    pub = await client.post(f"/api/v1/resources/{version_id}/publish")
    assert pub.status_code == 200, pub.text
    assert pub.json()["state"] == "published"


async def test_published_resource_listed(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    version_id = create.json()["id"]
    await client.post(f"/api/v1/resources/{version_id}/publish")

    listing = await client.get("/api/v1/resources")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert any(v["id"] == version_id for v in body["items"])


async def test_versions_endpoint_returns_history(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    body = create.json()
    base = body["base_resource_id"]
    await client.post(f"/api/v1/resources/{body['id']}/publish")

    new_ver = await client.post(
        f"/api/v1/resources/{base}/versions",
        json={"title": "Updated version"},
    )
    assert new_ver.status_code == 201, new_ver.text
    versions = await client.get(f"/api/v1/resources/{base}/versions")
    assert versions.status_code == 200
    ids = [v["id"] for v in versions.json()]
    assert len(ids) == 2


async def test_delete_resource_creates_tombstone(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    body = create.json()
    base = body["base_resource_id"]
    await client.post(f"/api/v1/resources/{body['id']}/publish")

    deleted = await client.delete(f"/api/v1/resources/{base}")
    assert deleted.status_code == 204

    get_resp = await client.get(f"/api/v1/resources/{body['id']}")
    assert get_resp.status_code == 410
    err = get_resp.json()
    assert err["error"] == "resource_deleted"
    assert "tombstone" in err["details"]
    tombstone = err["details"]["tombstone"]
    assert tombstone["title"] == VALID_PAYLOAD["title"]
    assert tombstone["data_deleted"] is True


async def test_unknown_resource_returns_404(client):
    resp = await client.get("/api/v1/resources/resource-does-not-exist")
    assert resp.status_code == 404
