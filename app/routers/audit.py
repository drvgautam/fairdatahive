from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db
from app.core.exceptions import ForbiddenError
from app.schemas.user import DownloadStats
from app.services import audit_service, resource_service
from app.services.resource_service import get_resource

router = APIRouter(tags=["audit"])


@router.get("/resources/{base_id}/stats", response_model=DownloadStats)
async def resource_stats(
    base_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resource = await get_resource(db, base_id)
    if resource.owner_sub != user.sub:
        raise ForbiddenError("Only the owner may view download statistics.")
    return await audit_service.stats_for_resource(db, base_id)


@router.get("/resources/{version_id}/downloads")
async def downloads(
    version_id: str,
    limit: int = 100,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    version = await resource_service.get_version(db, version_id, with_datasets=False)
    if version.publisher_sub != user.sub:
        raise ForbiddenError("Only the owner may view the download log.")
    rows = await audit_service.list_downloads(db, version_id, limit=limit)
    return [
        {
            "id": r.id,
            "user_sub": r.user_sub,
            "downloaded_at": r.downloaded_at.isoformat() if r.downloaded_at else None,
            "ip_address": r.ip_address,
            "user_agent": r.user_agent,
            "distribution_id": r.distribution_id,
        }
        for r in rows
    ]
