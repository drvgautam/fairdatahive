from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.services import cache_service
from app.services.object_storage_service import (
    BucketStatus,
    get_object_storage_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_STORAGE_CHECK_TIMEOUT_S = 5.0


async def _db_ok(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _storage_status() -> str:
    """Return the bucket status value ('ok', 'missing', 'denied', 'unreachable')."""
    try:
        storage = get_object_storage_service()
        return (
            await asyncio.wait_for(storage.check_bucket(), _STORAGE_CHECK_TIMEOUT_S)
        ).value
    except asyncio.TimeoutError:
        return BucketStatus.UNREACHABLE.value
    except Exception as exc:  # pragma: no cover - misconfiguration / missing SDK
        logger.warning("storage health check failed: %s", exc.__class__.__name__)
        return BucketStatus.UNREACHABLE.value


async def _components(db: AsyncSession) -> dict[str, str]:
    db_ok, cache_ok, storage = await asyncio.gather(
        _db_ok(db), cache_service.ping(), _storage_status()
    )
    return {
        "database": "ok" if db_ok else "down",
        "cache": "ok" if cache_ok else "down",
        "storage": storage,
    }


@router.get("/health", summary="Service health probe")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Liveness-style summary. Always 200; inspect ``components`` for detail.

    ``storage`` reports the bucket access status: ``ok``, ``missing`` (not
    provisioned), ``denied`` (credentials/policy), or ``unreachable``.
    """
    components = await _components(db)
    required_ok = components["database"] == "ok" and components["storage"] == "ok"
    return {
        "status": "ok" if required_ok else "degraded",
        "components": components,
    }


@router.get("/health/ready", summary="Readiness probe (503 when a dependency is down)")
async def ready(response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness for load balancers / orchestrators.

    Returns 503 when the database or the object storage bucket is not usable;
    the cache is reported but not required (search degrades gracefully).
    """
    components = await _components(db)
    ready_ok = components["database"] == "ok" and components["storage"] == "ok"
    if not ready_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready_ok else "not_ready", "components": components}
