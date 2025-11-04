from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LICENSE_VOCAB, THEME_LIST
from app.core.dependencies import get_db
from app.schemas.fair import LicenseInfo, ThemeInfo
from app.schemas.search import CatalogStats
from app.services.rdf_service import catalog_to_graph, to_jsonld, to_turtle
from app.services.search_service import catalog_stats

router = APIRouter(tags=["catalog"])


@router.get("/catalog")
async def get_catalog(
    scope: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    from app.services.resource_service import list_published

    items, total = await list_published(db, scope=scope, page=1, size=100)
    return {
        "total": total,
        "items": [
            {
                "id": v.id,
                "base_resource_id": v.base_resource_id,
                "title": v.title,
                "description": v.description,
                "theme": v.theme,
                "license_id": v.license_id,
                "publisher_sub": v.publisher_sub,
                "issued": v.issued.isoformat() if v.issued else None,
            }
            for v in items
        ],
    }


@router.get("/catalog.ttl")
async def catalog_ttl(
    scope: str | None = None, db: AsyncSession = Depends(get_db)
):
    graph = await catalog_to_graph(db, scope=scope)
    return Response(to_turtle(graph), media_type="text/turtle")


@router.get("/catalog.jsonld")
async def catalog_jsonld(
    scope: str | None = None, db: AsyncSession = Depends(get_db)
):
    graph = await catalog_to_graph(db, scope=scope)
    return Response(to_jsonld(graph), media_type="application/ld+json")


@router.get("/catalog/stats", response_model=CatalogStats)
async def stats(db: AsyncSession = Depends(get_db)):
    return await catalog_stats(db)


@router.get("/licenses", response_model=list[LicenseInfo])
async def licenses() -> list[LicenseInfo]:
    return [LicenseInfo(**v) for v in LICENSE_VOCAB.values()]


@router.get("/themes", response_model=list[ThemeInfo])
async def themes() -> list[ThemeInfo]:
    return [ThemeInfo(**t) for t in THEME_LIST]
