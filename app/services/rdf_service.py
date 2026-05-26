from __future__ import annotations

import json
import logging
from datetime import datetime

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, RDF, XSD
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.resource_service import version_relations_options

from app.config import settings
from app.core.catalog_visibility import public_catalog_version_filters
from app.core.constants import LICENSE_VOCAB
from app.models.dataset import Dataset, Distribution
from app.models.resource import Resource, ResourceVersion
from app.models.user import UserProfile

logger = logging.getLogger(__name__)

SPDX = Namespace("http://spdx.org/rdf/terms#")
APP = Namespace("https://fairdatahive.io/vocab#")


def _bind_namespaces(g: Graph) -> None:
    g.bind("dcat", DCAT)
    g.bind("dcterms", DCTERMS)
    g.bind("foaf", FOAF)
    g.bind("xsd", XSD)
    g.bind("spdx", SPDX)
    g.bind("app", APP)


def _base(path: str = "") -> str:
    return f"{settings.base_url.rstrip('/')}{path}"


def resource_iri(resource_id: str) -> URIRef:
    return URIRef(f"{_base('/api/v1/resources')}/{resource_id}")


def version_iri(version_id: str) -> URIRef:
    return URIRef(f"{_base('/api/v1/resources')}/{version_id}")


def distribution_iri(distribution_id: str) -> URIRef:
    return URIRef(f"{_base('/api/v1/distributions')}/{distribution_id}")


def dataset_iri(dataset_id: str) -> URIRef:
    return URIRef(f"{_base('/api/v1/datasets')}/{dataset_id}")


def user_iri(sub: str) -> URIRef:
    return URIRef(f"{_base('/api/v1/users')}/{sub}")


def catalog_iri() -> URIRef:
    return URIRef(_base("/api/v1/catalog"))


def license_iri(license_id: str | None) -> URIRef | None:
    if license_id is None:
        return None
    info = LICENSE_VOCAB.get(license_id)
    if info is None:
        return URIRef(f"https://spdx.org/licenses/{license_id}")
    return URIRef(info["url"])


def _add_literal(g: Graph, subj, pred, value, datatype=None, lang=None) -> None:
    if value is None:
        return
    g.add((subj, pred, Literal(value, datatype=datatype, lang=lang)))


def _publisher_node(
    g: Graph, sub: str, profile: UserProfile | None
) -> URIRef:
    node = user_iri(sub)
    if (node, RDF.type, FOAF.Agent) in g:
        return node
    g.add((node, RDF.type, FOAF.Agent))
    name = (profile.display_name if profile else None) or sub
    g.add((node, FOAF.name, Literal(name)))
    if profile and profile.email:
        g.add((node, FOAF.mbox, URIRef(f"mailto:{profile.email}")))
    return node


def _add_distribution(
    g: Graph, version: ResourceVersion, distribution: Distribution
) -> None:
    node = distribution_iri(distribution.id)
    g.add((node, RDF.type, DCAT.Distribution))
    _add_literal(g, node, DCTERMS.title, distribution.title)
    _add_literal(g, node, DCTERMS.description, distribution.description)
    if distribution.media_type:
        g.add(
            (
                node,
                DCAT.mediaType,
                URIRef(f"https://www.iana.org/assignments/media-types/{distribution.media_type}"),
            )
        )
    if distribution.byte_size is not None:
        g.add((node, DCAT.byteSize, Literal(distribution.byte_size, datatype=XSD.decimal)))
    if distribution.checksum_sha256:
        bnode = BNode()
        g.add((node, SPDX.checksum, bnode))
        g.add((bnode, RDF.type, SPDX.Checksum))
        g.add(
            (
                bnode,
                SPDX.checksumAlgorithm,
                URIRef("http://spdx.org/rdf/terms#checksumAlgorithm_sha256"),
            )
        )
        g.add((bnode, SPDX.checksumValue, Literal(distribution.checksum_sha256)))
    if not version.data_deleted:
        if distribution.access_url:
            g.add((node, DCAT.accessURL, URIRef(distribution.access_url)))
        if distribution.download_url and distribution.dist_type != "upload":
            g.add((node, DCAT.downloadURL, URIRef(distribution.download_url)))
        else:
            g.add(
                (
                    node,
                    DCAT.downloadURL,
                    URIRef(f"{_base('/api/v1/distributions')}/{distribution.id}/download"),
                )
            )

    if distribution.data_service is not None:
        ds = distribution.data_service
        ds_node = URIRef(f"{_base('/api/v1/data-services')}/{ds.id}")
        g.add((node, DCAT.accessService, ds_node))
        g.add((ds_node, RDF.type, DCAT.DataService))
        g.add((ds_node, DCAT.endpointURL, URIRef(ds.endpoint_url)))
        _add_literal(g, ds_node, DCTERMS.description, ds.description)


def _add_version(
    g: Graph,
    version: ResourceVersion,
    publisher_profile: UserProfile | None,
) -> URIRef:
    node = version_iri(version.id)
    g.add((node, RDF.type, DCAT.Resource))
    g.add((node, DCTERMS.isVersionOf, resource_iri(version.base_resource_id)))
    if version.previous_version_id:
        g.add((node, DCTERMS.replaces, version_iri(version.previous_version_id)))

    _add_literal(g, node, DCTERMS.title, version.title, lang=version.language or None)
    _add_literal(g, node, DCTERMS.description, version.description)
    if version.issued:
        g.add(
            (
                node,
                DCTERMS.issued,
                Literal(version.issued.isoformat(), datatype=XSD.dateTime),
            )
        )
    if version.modified:
        g.add(
            (
                node,
                DCTERMS.modified,
                Literal(version.modified.isoformat(), datatype=XSD.dateTime),
            )
        )

    if version.theme:
        g.add((node, DCAT.theme, Literal(version.theme)))
    for kw in version.keywords or []:
        g.add((node, DCAT.keyword, Literal(kw)))

    lic = license_iri(version.license_id)
    if lic is not None:
        g.add((node, DCTERMS.license, lic))

    if version.language:
        g.add((node, DCTERMS.language, Literal(version.language)))
    if version.doi:
        if version.doi.startswith("http"):
            g.add((node, DCTERMS.identifier, URIRef(version.doi)))
        else:
            g.add((node, DCTERMS.identifier, URIRef(f"https://doi.org/{version.doi}")))

    if version.provenance:
        g.add((node, DCTERMS.provenance, Literal(version.provenance)))
    if version.rights_statement:
        g.add((node, DCTERMS.rights, Literal(version.rights_statement)))
    if version.spatial:
        g.add((node, DCTERMS.spatial, Literal(version.spatial)))
    if version.temporal:
        g.add((node, DCTERMS.temporal, Literal(version.temporal)))

    if version.assumptions:
        g.add((node, APP.assumptions, Literal(version.assumptions)))
    if version.technique:
        g.add((node, APP.technique, Literal(version.technique)))
    if version.post_processing:
        g.add((node, APP.postProcessing, Literal(version.post_processing)))

    if version.data_deleted:
        g.add((node, APP.deleted, Literal(True, datatype=XSD.boolean)))

    publisher = _publisher_node(g, version.publisher_sub, publisher_profile)
    g.add((node, DCTERMS.publisher, publisher))

    for dataset in version.datasets:
        ds_node = dataset_iri(dataset.id)
        g.add((node, DCAT.dataset, ds_node))
        g.add((ds_node, RDF.type, DCAT.Dataset))
        for dist in dataset.distributions:
            g.add((ds_node, DCAT.distribution, distribution_iri(dist.id)))
            g.add((node, DCAT.distribution, distribution_iri(dist.id)))
            _add_distribution(g, version, dist)
    return node


async def version_to_graph(
    db: AsyncSession, version: ResourceVersion
) -> Graph:
    g = Graph()
    _bind_namespaces(g)
    profile = await db.get(UserProfile, version.publisher_sub)
    _add_version(g, version, profile)
    return g


async def catalog_to_graph(
    db: AsyncSession, *, scope: str | None = None, limit: int | None = None
) -> Graph:
    g = Graph()
    _bind_namespaces(g)

    cat = catalog_iri()
    g.add((cat, RDF.type, DCAT.Catalog))
    g.add((cat, DCTERMS.title, Literal("FairDataHive Catalog")))
    g.add((cat, DCTERMS.description, Literal("FAIR research data catalog.")))

    stmt = (
        select(ResourceVersion)
        .join(Resource, Resource.current_version_id == ResourceVersion.id)
        .where(*public_catalog_version_filters())
        .options(version_relations_options())
        .order_by(ResourceVersion.issued.desc())
    )
    if scope:
        stmt = stmt.where(Resource.scope == scope)
    if limit:
        stmt = stmt.limit(limit)

    versions = list((await db.execute(stmt)).scalars().all())
    profiles: dict[str, UserProfile | None] = {}
    for v in versions:
        if v.publisher_sub not in profiles:
            profiles[v.publisher_sub] = await db.get(UserProfile, v.publisher_sub)
        node = _add_version(g, v, profiles[v.publisher_sub])
        g.add((cat, DCAT.dataset, node))
    return g


def to_turtle(g: Graph) -> str:
    return g.serialize(format="turtle")


def to_jsonld(g: Graph, *, context: dict | None = None) -> str:
    if context is None:
        context = {
            "dcat": str(DCAT),
            "dcterms": str(DCTERMS),
            "foaf": str(FOAF),
            "xsd": str(XSD),
            "spdx": str(SPDX),
            "app": str(APP),
        }
    data = g.serialize(format="json-ld", context=context, auto_compact=True)
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return data


def to_oai_dc(version: ResourceVersion, publisher_name: str | None) -> dict:
    """Plain dictionary representation for OAI-PMH Dublin Core serialization."""

    return {
        "identifier": str(version_iri(version.id)),
        "title": version.title,
        "description": version.description,
        "creator": publisher_name or version.publisher_sub,
        "date": version.issued.isoformat() if version.issued else None,
        "subject": list(version.keywords or []) + (
            [version.theme] if version.theme else []
        ),
        "rights": (
            LICENSE_VOCAB.get(version.license_id, {}).get("url")
            if version.license_id
            else None
        ),
        "language": version.language,
        "type": "Dataset",
        "format": list(
            {
                d.media_type
                for ds in version.datasets
                for d in ds.distributions
                if d.media_type
            }
        ),
    }
