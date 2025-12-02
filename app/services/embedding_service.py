from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session_factory
from app.models.resource import ResourceVersion

logger = logging.getLogger(__name__)


_pending_tasks: set[asyncio.Task] = set()


@lru_cache(maxsize=1)
def _load_model() -> Any:
    from sentence_transformers import SentenceTransformer

    logger.info("Loading sentence-transformer model %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def _encode_sync(text: str) -> list[float]:
    model = _load_model()
    vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vec.tolist()


async def encode(text: str) -> list[float]:
    """Encode a single string to a 768-dimensional float vector.

    Runs the (CPU-bound) model in a thread-pool executor.
    """

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _encode_sync, text)


def _embedding_input(version: ResourceVersion) -> str:
    parts: list[str] = [version.title or "", version.description or ""]
    if version.keywords:
        parts.append(" ".join(version.keywords))
    if version.theme:
        parts.append(version.theme)
    return "\n".join(p for p in parts if p)


async def update_embedding(version_id: str) -> None:
    factory = get_session_factory()
    async with factory() as db:
        version = await db.get(ResourceVersion, version_id)
        if version is None:
            return
        text = _embedding_input(version)
        try:
            vec = await encode(text)
        except Exception as exc:  # pragma: no cover - model load may fail in tests
            logger.warning("Embedding failed for %s: %s", version_id, exc)
            return
        version.embedding = vec
        await db.commit()


async def schedule_embedding_update(version_id: str) -> None:
    """Fire-and-forget background embedding update.

    Stored on the module-level set so the task is not garbage-collected.
    """

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    task = loop.create_task(update_embedding(version_id))
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


async def search_by_vector(
    db: AsyncSession,
    query_vector: list[float],
    *,
    scope: str | None = None,
    threshold: float = 0.30,
    limit: int = 20,
) -> list[tuple[ResourceVersion, float]]:
    """Cosine-similarity search via pgvector. Returns (version, similarity)."""

    from sqlalchemy import literal

    # pgvector exposes <=> as cosine distance; similarity = 1 - distance.
    distance = ResourceVersion.embedding.op("<=>")(literal(query_vector))
    similarity = (literal(1.0) - distance).label("similarity")

    stmt = (
        select(ResourceVersion, similarity)
        .where(ResourceVersion.embedding.is_not(None))
        .where(ResourceVersion.state == "published")
        .where(ResourceVersion.data_deleted.is_(False))
    )
    if scope is not None:
        from app.models.resource import Resource

        stmt = stmt.join(Resource, Resource.current_version_id == ResourceVersion.id)
        stmt = stmt.where(Resource.scope == scope)

    stmt = (
        stmt.where(similarity >= literal(threshold))
        .order_by(similarity.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [(row[0], float(row[1])) for row in result.all()]
