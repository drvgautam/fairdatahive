from __future__ import annotations

import pytest

from tests.test_resources import VALID_PAYLOAD

pytestmark = pytest.mark.asyncio


async def test_oai_identify(client):
    resp = await client.get("/api/v1/oai?verb=Identify")
    assert resp.status_code == 200
    assert "OAI-PMH" in resp.text
    assert "Identify" in resp.text


async def test_oai_list_metadata_formats(client):
    resp = await client.get("/api/v1/oai?verb=ListMetadataFormats")
    assert resp.status_code == 200
    assert "oai_dc" in resp.text


async def test_oai_list_records_includes_published(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    body = create.json()
    await client.post(f"/api/v1/resources/{body['id']}/publish")

    resp = await client.get(
        "/api/v1/oai?verb=ListRecords&metadataPrefix=oai_dc"
    )
    assert resp.status_code == 200
    assert "record" in resp.text
    assert body["id"] in resp.text


async def test_oai_bad_verb(client):
    resp = await client.get("/api/v1/oai?verb=Nope")
    assert resp.status_code == 200
    assert "badVerb" in resp.text


async def test_oai_missing_metadata_prefix(client):
    resp = await client.get("/api/v1/oai?verb=ListRecords")
    assert resp.status_code == 200
    assert "badArgument" in resp.text
