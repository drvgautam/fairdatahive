from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.services import cache_service

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health probe")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    cache_ok = await cache_service.ping()

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "components": {
            "database": "ok" if db_ok else "down",
            "cache": "ok" if cache_ok else "down",
        },
    }
