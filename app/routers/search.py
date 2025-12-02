from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.pagination import PageParams, get_page_params
from app.schemas.search import SearchResponse, SuggestResponse
from app.services import cache_service, search_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str | None = Query(default=None),
    mode: Literal["auto", "keyword", "semantic"] = Query(default="auto"),
    scope: str | None = Query(default=None),
    theme: str | None = Query(default=None),
    license_id: str | None = Query(default=None),
    params: PageParams = Depends(get_page_params),
    db: AsyncSession = Depends(get_db),
):
    cache_payload = {
        "q": q or "",
        "mode": mode,
        "scope": scope,
        "theme": theme,
        "license_id": license_id,
        "page": params.page,
        "size": params.size,
    }
    prefix = "search:sem" if mode == "semantic" else "search:kw"
    key = cache_service.make_cache_key(prefix, scope, cache_payload)
    cached = await cache_service.get_json(key)
    if cached is not None:
        return SearchResponse.model_validate(cached)

    result = await search_service.unified_search(
        db,
        q=q,
        mode=mode,
        scope=scope,
        theme=theme,
        license_id=license_id,
        page=params.page,
        size=params.size,
    )
    ttl = 120 if mode == "semantic" or result.mode_used == "semantic" else 300
    await cache_service.set_json(key, result.model_dump(mode="json"), ttl)
    return result


@router.get("/search/suggest", response_model=SuggestResponse)
async def suggest(
    q: str = Query(min_length=2),
    scope: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
):
    suggestions = await search_service.suggest(
        db, prefix=q, scope=scope, limit=limit
    )
    return SuggestResponse(suggestions=suggestions)
