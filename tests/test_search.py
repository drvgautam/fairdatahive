from __future__ import annotations

import pytest

from tests.test_resources import VALID_PAYLOAD

pytestmark = pytest.mark.asyncio


async def _publish_with_title(client, title: str, description: str | None = None):
    payload = {
        **VALID_PAYLOAD,
        "title": title,
        "description": description or VALID_PAYLOAD["description"],
    }
    create = await client.post("/api/v1/resources", json=payload)
    body = create.json()
    await client.post(f"/api/v1/resources/{body['id']}/publish")
    return body["id"]


async def test_empty_search_returns_all_published(client):
    await _publish_with_title(client, "Corrosion impedance study")
    resp = await client.get("/api/v1/search")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["mode_used"] == "keyword"


async def test_keyword_search_filters_by_query(client):
    await _publish_with_title(client, "Corrosion impedance study")
    await _publish_with_title(client, "Unrelated dataset of cats")

    resp = await client.get("/api/v1/search?q=corrosion")
    assert resp.status_code == 200
    data = resp.json()
    titles = [hit["resource"]["title"] for hit in data["results"]]
    assert any("Corrosion" in t for t in titles)
    assert not any("cats" in t for t in titles)


async def _publish_with_keywords(client, keywords: list[str]):
    payload = {
        **VALID_PAYLOAD,
        "title": "Dataset without keyword letters in title",
        "description": (
            "Neutral description that does not mention the short keyword tokens."
        ),
        "keywords": keywords,
    }
    create = await client.post("/api/v1/resources", json=payload)
    body = create.json()
    await client.post(f"/api/v1/resources/{body['id']}/publish")
    return body["id"]


async def test_keyword_search_matches_short_keywords(client):
    await _publish_with_keywords(client, ["a", "b", "c", "d"])
    await _publish_with_keywords(client, ["x", "y"])

    abcd_title = "Dataset without keyword letters in title"
    for query in ("a,b,c,d", "a b c d", "a"):
        resp = await client.get(f"/api/v1/search?q={query}&mode=keyword")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        titles = [hit["resource"]["title"] for hit in data["results"]]
        assert any(abcd_title in t for t in titles), (
            f"expected abcd dataset for query {query!r}, got {titles!r}"
        )


async def test_keyword_search_matches_stored_keyword_terms(client):
    await _publish_with_keywords(client, ["electrochemistry", "impedance"])
    resp = await client.get("/api/v1/search?q=impedance&mode=keyword")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_search_suggest(client):
    await _publish_with_title(client, "Corrosion impedance study")
    resp = await client.get("/api/v1/search/suggest?q=corr")
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert any("Corrosion" in s for s in suggestions)


async def test_catalog_stats(client):
    await _publish_with_title(client, "Corrosion impedance study")
    resp = await client.get("/api/v1/catalog/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_published"] >= 1
    assert data["total_resources"] >= 1


async def test_licenses_endpoint(client):
    resp = await client.get("/api/v1/licenses")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    assert "CC-BY-4.0" in ids
    assert "MIT" in ids


async def test_themes_endpoint(client):
    resp = await client.get("/api/v1/themes")
    assert resp.status_code == 200
    labels = [item["label"] for item in resp.json()]
    assert any("Electro" in s for s in labels)
