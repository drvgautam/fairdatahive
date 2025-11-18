from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.dependencies import get_db
from app.services.fair_service import compute_fair_score
from app.services.rdf_service import to_jsonld, to_turtle, version_to_graph
from app.services import resource_service

router = APIRouter(prefix="/resources", tags=["rdf"])

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/{version_id}.ttl")
async def version_ttl(version_id: str, db: AsyncSession = Depends(get_db)):
    version = await resource_service.get_version(db, version_id)
    graph = await version_to_graph(db, version)
    return Response(to_turtle(graph), media_type="text/turtle")


@router.get("/{version_id}.jsonld")
async def version_jsonld(version_id: str, db: AsyncSession = Depends(get_db)):
    version = await resource_service.get_version(db, version_id)
    graph = await version_to_graph(db, version)
    return Response(to_jsonld(graph), media_type="application/ld+json")


@router.get("/{version_id}/landing", response_class=HTMLResponse)
async def landing_page(
    version_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    version = await resource_service.get_version(db, version_id)
    graph = await version_to_graph(db, version)
    jsonld = to_jsonld(graph)
    fair = await compute_fair_score(db, version)
    versions = await resource_service.list_versions(db, version.base_resource_id)
    return _TEMPLATES.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "version": version,
            "jsonld": jsonld,
            "fair": fair,
            "versions": versions,
        },
    )
