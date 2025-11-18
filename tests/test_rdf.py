from __future__ import annotations

import pytest
from rdflib import Graph
from rdflib.namespace import DCAT, DCTERMS, RDF

pytestmark = pytest.mark.asyncio

from tests.test_resources import VALID_PAYLOAD


async def test_resource_turtle_round_trips(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    version_id = create.json()["id"]
    await client.post(f"/api/v1/resources/{version_id}/publish")

    ttl = await client.get(f"/api/v1/resources/{version_id}.ttl")
    assert ttl.status_code == 200
    assert "text/turtle" in ttl.headers["content-type"]

    g = Graph()
    g.parse(data=ttl.text, format="turtle")
    iri = None
    for s, _, _ in g.triples((None, RDF.type, DCAT.Resource)):
        iri = s
        break
    assert iri is not None
    titles = list(g.objects(iri, DCTERMS.title))
    assert any(VALID_PAYLOAD["title"] in str(t) for t in titles)


async def test_resource_jsonld_parses(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    version_id = create.json()["id"]
    await client.post(f"/api/v1/resources/{version_id}/publish")

    jl = await client.get(f"/api/v1/resources/{version_id}.jsonld")
    assert jl.status_code == 200
    assert "application/ld+json" in jl.headers["content-type"]

    g = Graph()
    g.parse(data=jl.text, format="json-ld")
    titles = [
        str(o)
        for o in g.objects(None, DCTERMS.title)
    ]
    assert any(VALID_PAYLOAD["title"] in t for t in titles)


async def test_catalog_turtle_contains_published_resource(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    version_id = create.json()["id"]
    await client.post(f"/api/v1/resources/{version_id}/publish")

    catalog = await client.get("/api/v1/catalog.ttl")
    assert catalog.status_code == 200
    g = Graph()
    g.parse(data=catalog.text, format="turtle")
    catalogs = list(g.subjects(RDF.type, DCAT.Catalog))
    assert catalogs, "catalog node missing"
    datasets = list(g.objects(catalogs[0], DCAT.dataset))
    assert any(version_id in str(d) for d in datasets)


async def test_content_negotiation_on_resource_endpoint(client):
    create = await client.post("/api/v1/resources", json=VALID_PAYLOAD)
    version_id = create.json()["id"]
    await client.post(f"/api/v1/resources/{version_id}/publish")

    ttl = await client.get(
        f"/api/v1/resources/{version_id}",
        headers={"Accept": "text/turtle"},
    )
    assert ttl.status_code == 200
    assert ttl.headers["content-type"].startswith("text/turtle")
