from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy import case, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.dataset import Dataset, Distribution
from app.models.resource import Resource, ResourceVersion
from app.schemas.search import (
    CatalogStats,
    FacetEntry,
    FacetGroup,
    SearchHit,
    SearchResponse,
)
from app.schemas.resource import ResourceVersionSummary

logger = logging.getLogger(__name__)


def _published_base():
    return (
        select(ResourceVersion)
        .join(Resource, Resource.current_version_id == ResourceVersion.id)
        .where(ResourceVersion.state == "published")
        .where(ResourceVersion.data_deleted.is_(False))
    )


def _scope_filter(stmt, scope: str | None):
    if scope:
        stmt = stmt.where(Resource.scope == scope)
    return stmt


def _facet_filter(stmt, *, theme: str | None, license_id: str | None):
    if theme:
        stmt = stmt.where(ResourceVersion.theme == theme)
    if license_id:
        stmt = stmt.where(ResourceVersion.license_id == license_id)
    return stmt


def _fts_vector():
    """tsvector over title + description (matches idx_rv_fts GIN index)."""
    combined = (
        func.coalesce(ResourceVersion.title, "")
        .op("||")(literal(" "))
        .op("||")(func.coalesce(ResourceVersion.description, ""))
    )
    return func.to_tsvector("english", combined)


async def keyword_search(
    db: AsyncSession,
    *,
    q: str,
    scope: str | None,
    theme: str | None,
    license_id: str | None,
    page: int,
    size: int,
) -> tuple[list[tuple[ResourceVersion, float]], int]:
    bind = db.bind
    dialect = bind.dialect.name if bind is not None else "postgresql"

    base = _published_base()
    base = _scope_filter(base, scope)
    base = _facet_filter(base, theme=theme, license_id=license_id)

    # PostgreSQL FTS: select id + score only, then load entities (avoids
    # selectinload + add_columns incompatibility on ORM queries).
    if dialect == "postgresql" and q:
        tsv = _fts_vector()
        tsquery = func.plainto_tsquery("english", q)
        score = func.ts_rank(tsv, tsquery).label("score")
        ranked = (
            select(ResourceVersion.id, score)
            .select_from(ResourceVersion)
            .join(Resource, Resource.current_version_id == ResourceVersion.id)
            .where(ResourceVersion.state == "published")
            .where(ResourceVersion.data_deleted.is_(False))
        )
        if scope:
            ranked = ranked.where(Resource.scope == scope)
        if theme:
            ranked = ranked.where(ResourceVersion.theme == theme)
        if license_id:
            ranked = ranked.where(ResourceVersion.license_id == license_id)
        ranked = ranked.where(tsv.op("@@")(tsquery))

        total = int(
            (await db.execute(select(func.count()).select_from(ranked.subquery()))).scalar()
            or 0
        )
        page_stmt = (
            ranked.order_by(score.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        id_rows = (await db.execute(page_stmt)).all()
        if not id_rows:
            return [], total

        id_to_score = {row[0]: float(row[1]) for row in id_rows}
        versions_stmt = select(ResourceVersion).where(
            ResourceVersion.id.in_(id_to_score.keys())
        )
        versions = {
            v.id: v for v in (await db.execute(versions_stmt)).scalars().all()
        }
        out = [
            (versions[vid], id_to_score[vid])
            for vid in id_to_score
            if vid in versions
        ]
        out.sort(key=lambda pair: pair[1], reverse=True)
        return out, total

    # SQLite / fallback: LIKE filter (no eager-load; summary only needs columns).
    pattern = f"%{q.lower()}%" if q else None
    score_expr = literal(1.0).label("score")
    if pattern:
        base = base.where(
            or_(
                func.lower(ResourceVersion.title).like(pattern),
                func.lower(ResourceVersion.description).like(pattern),
            )
        )
    base = base.add_columns(score_expr)

    total = int(
        (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
        or 0
    )
    items_stmt = (
        base.order_by(ResourceVersion.modified.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await db.execute(items_stmt)).all()
    out: list[tuple[ResourceVersion, float]] = []
    for row in rows:
        version = row[0]
        score_val = float(row[1]) if len(row) > 1 and row[1] is not None else 0.0
        out.append((version, score_val))
    return out, total


async def semantic_search(
    db: AsyncSession,
    *,
    q: str,
    scope: str | None,
    threshold: float | None,
    limit: int,
) -> list[tuple[ResourceVersion, float]]:
    from app.services import embedding_service

    bind = db.bind
    if bind is not None and bind.dialect.name != "postgresql":
        return []

    try:
        vec = await embedding_service.encode(q)
    except Exception as exc:
        logger.warning("Semantic search disabled (encode failed): %s", exc)
        return []

    th = threshold if threshold is not None else settings.semantic_search_threshold
    return await embedding_service.search_by_vector(
        db, vec, scope=scope, threshold=th, limit=limit
    )


async def compute_facets(
    db: AsyncSession,
    *,
    scope: str | None,
    base_query=None,
) -> FacetGroup:
    base = base_query if base_query is not None else _published_base()
    base = _scope_filter(base, scope)
    base_subq = base.subquery()

    theme_stmt = (
        select(base_subq.c.theme, func.count().label("count"))
        .where(base_subq.c.theme.is_not(None))
        .group_by(base_subq.c.theme)
        .order_by(func.count().desc())
        .limit(20)
    )
    license_stmt = (
        select(base_subq.c.license_id, func.count().label("count"))
        .where(base_subq.c.license_id.is_not(None))
        .group_by(base_subq.c.license_id)
        .order_by(func.count().desc())
        .limit(20)
    )

    themes = [
        FacetEntry(value=row[0], count=int(row[1]))
        for row in (await db.execute(theme_stmt)).all()
    ]
    licenses = [
        FacetEntry(value=row[0], count=int(row[1]))
        for row in (await db.execute(license_stmt)).all()
    ]

    fmt_stmt = (
        select(Distribution.media_type, func.count().label("count"))
        .join(Dataset, Dataset.id == Distribution.dataset_id)
        .join(ResourceVersion, ResourceVersion.id == Dataset.resource_version_id)
        .join(Resource, Resource.current_version_id == ResourceVersion.id)
        .where(ResourceVersion.state == "published")
        .where(ResourceVersion.data_deleted.is_(False))
        .where(Distribution.media_type.is_not(None))
    )
    if scope:
        fmt_stmt = fmt_stmt.where(Resource.scope == scope)
    fmt_stmt = (
        fmt_stmt.group_by(Distribution.media_type)
        .order_by(func.count().desc())
        .limit(20)
    )
    formats = [
        FacetEntry(value=row[0], count=int(row[1]))
        for row in (await db.execute(fmt_stmt)).all()
    ]

    return FacetGroup(themes=themes, licenses=licenses, formats=formats)


def _version_to_summary(v: ResourceVersion) -> ResourceVersionSummary:
    return ResourceVersionSummary.model_validate(v)


async def unified_search(
    db: AsyncSession,
    *,
    q: str | None,
    mode: Literal["auto", "keyword", "semantic"],
    scope: str | None,
    theme: str | None,
    license_id: str | None,
    page: int,
    size: int,
) -> SearchResponse:
    if not q or not q.strip():
        items, total = await keyword_search(
            db,
            q="",
            scope=scope,
            theme=theme,
            license_id=license_id,
            page=page,
            size=size,
        )
        facets = await compute_facets(db, scope=scope)
        return SearchResponse(
            total=total,
            page=page,
            size=size,
            mode_used="keyword",
            results=[
                SearchHit(resource=_version_to_summary(v), score=s) for v, s in items
            ],
            facets=facets,
        )

    if mode == "semantic":
        sem = await semantic_search(
            db, q=q, scope=scope, threshold=None, limit=size
        )
        facets = await compute_facets(db, scope=scope)
        return SearchResponse(
            total=len(sem),
            page=1,
            size=size,
            mode_used="semantic",
            results=[
                SearchHit(resource=_version_to_summary(v), score=s) for v, s in sem
            ],
            facets=facets,
        )

    items, total = await keyword_search(
        db,
        q=q,
        scope=scope,
        theme=theme,
        license_id=license_id,
        page=page,
        size=size,
    )

    if mode == "keyword" or total >= 3:
        facets = await compute_facets(db, scope=scope)
        return SearchResponse(
            total=total,
            page=page,
            size=size,
            mode_used="keyword",
            results=[
                SearchHit(resource=_version_to_summary(v), score=s) for v, s in items
            ],
            facets=facets,
        )

    sem = await semantic_search(db, q=q, scope=scope, threshold=None, limit=size)
    seen_ids = {v.id for v, _ in items}
    merged: list[tuple[ResourceVersion, float]] = list(items)
    for v, s in sem:
        if v.id not in seen_ids:
            merged.append((v, s))
            seen_ids.add(v.id)

    facets = await compute_facets(db, scope=scope)
    return SearchResponse(
        total=len(merged),
        page=1,
        size=size,
        mode_used="auto",
        results=[
            SearchHit(resource=_version_to_summary(v), score=s) for v, s in merged
        ],
        facets=facets,
    )


async def suggest(
    db: AsyncSession,
    *,
    prefix: str,
    scope: str | None,
    limit: int = 10,
) -> list[str]:
    if not prefix or len(prefix) < 2:
        return []
    pat = f"{prefix.lower()}%"
    stmt = (
        _published_base()
        .with_only_columns(ResourceVersion.title)
        .where(func.lower(ResourceVersion.title).like(pat))
        .limit(limit)
    )
    stmt = _scope_filter(stmt, scope)
    titles = [row[0] for row in (await db.execute(stmt)).all() if row[0]]
    return titles


async def catalog_stats(db: AsyncSession) -> CatalogStats:
    res_total = int(
        (await db.execute(select(func.count(Resource.id)))).scalar() or 0
    )
    ver_total = int(
        (await db.execute(select(func.count(ResourceVersion.id)))).scalar() or 0
    )
    published = int(
        (
            await db.execute(
                select(func.count(ResourceVersion.id)).where(
                    ResourceVersion.state == "published"
                )
            )
        ).scalar()
        or 0
    )
    drafts = int(
        (
            await db.execute(
                select(func.count(ResourceVersion.id)).where(
                    ResourceVersion.state == "draft"
                )
            )
        ).scalar()
        or 0
    )
    dists = int(
        (await db.execute(select(func.count(Distribution.id)))).scalar() or 0
    )

    theme_stmt = (
        select(ResourceVersion.theme, func.count().label("count"))
        .where(ResourceVersion.state == "published")
        .where(ResourceVersion.theme.is_not(None))
        .group_by(ResourceVersion.theme)
        .order_by(func.count().desc())
    )
    license_stmt = (
        select(ResourceVersion.license_id, func.count().label("count"))
        .where(ResourceVersion.state == "published")
        .where(ResourceVersion.license_id.is_not(None))
        .group_by(ResourceVersion.license_id)
        .order_by(func.count().desc())
    )
    by_theme = [
        FacetEntry(value=r[0], count=int(r[1]))
        for r in (await db.execute(theme_stmt)).all()
    ]
    by_license = [
        FacetEntry(value=r[0], count=int(r[1]))
        for r in (await db.execute(license_stmt)).all()
    ]

    return CatalogStats(
        total_resources=res_total,
        total_versions=ver_total,
        total_published=published,
        total_drafts=drafts,
        total_distributions=dists,
        by_theme=by_theme,
        by_license=by_license,
    )
