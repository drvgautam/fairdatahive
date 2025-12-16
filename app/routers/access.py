from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db,
    get_optional_user,
)
from app.schemas.access import (
    AccessRequestCreate,
    AccessRequestRead,
    AccessStatus,
)
from app.services import access_service

router = APIRouter(tags=["access"])


@router.get(
    "/resources/{version_id}/access",
    response_model=AccessStatus,
)
async def access_status(
    version_id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    status_data = await access_service.get_access_status(
        db, version_id, user.sub if user else None
    )
    return AccessStatus(**status_data)


@router.post(
    "/access-requests",
    response_model=AccessRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_access_request(
    payload: AccessRequestCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await access_service.create_request(
        db,
        version_id=payload.resource_version_id,
        requester_sub=user.sub,
        message=payload.message,
    )


@router.get(
    "/access-requests/incoming",
    response_model=list[AccessRequestRead],
)
async def incoming(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await access_service.list_incoming(db, user.sub)


@router.get(
    "/access-requests/outgoing",
    response_model=list[AccessRequestRead],
)
async def outgoing(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await access_service.list_outgoing(db, user.sub)


@router.post(
    "/access-requests/{request_id}/accept",
    response_model=AccessRequestRead,
)
async def accept(
    request_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await access_service.accept(db, request_id, user.sub)


@router.post(
    "/access-requests/{request_id}/reject",
    response_model=AccessRequestRead,
)
async def reject(
    request_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await access_service.reject(db, request_id, user.sub)


@router.delete(
    "/access-requests/{request_id}/revoke",
    response_model=AccessRequestRead,
)
async def revoke(
    request_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await access_service.revoke(db, request_id, user.sub)
