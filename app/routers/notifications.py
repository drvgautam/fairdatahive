from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.schemas.notification import NotificationRead
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    unread_only: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.list_for_user(
        db, user.sub, unread_only=unread_only
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    n = await notification_service.mark_read(db, notification_id, user.sub)
    if n is None:
        raise NotFoundError(
            f"Notification {notification_id} not found.",
            error_code="notification_not_found",
        )
    return n


@router.post("/read-all")
async def read_all(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await notification_service.mark_all_read(db, user.sub)
    return {"updated": count}
