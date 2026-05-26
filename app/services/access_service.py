from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.database import get_session_factory
from app.models.access import AccessRequest
from app.models.resource import ResourceVersion
from app.services import notification_service
from app.core.resource_access import get_version_if_viewable
from app.services.resource_service import get_version

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_access_status(
    db: AsyncSession, version_id: str, user_sub: str | None
) -> dict:
    version = await get_version_if_viewable(
        db, version_id, user_sub, with_datasets=False
    )
    is_owner = user_sub is not None and version.publisher_sub == user_sub
    has_access = (
        not version.is_private
        or is_owner
        or (user_sub is not None and user_sub in (version.access_rights or []))
    )
    pending_id: int | None = None
    if user_sub is not None and version.is_private and not is_owner:
        stmt = select(AccessRequest.id).where(
            AccessRequest.resource_version_id == version_id,
            AccessRequest.requester_sub == user_sub,
            AccessRequest.status == "pending",
        )
        pending_id = (await db.execute(stmt)).scalar_one_or_none()
    return {
        "resource_version_id": version.id,
        "is_private": version.is_private,
        "has_access": has_access,
        "is_owner": is_owner,
        "pending_request_id": pending_id,
    }


async def create_request(
    db: AsyncSession,
    *,
    version_id: str,
    requester_sub: str,
    message: str | None,
) -> AccessRequest:
    version = await get_version(db, version_id, with_datasets=False)

    if not version.is_private:
        raise ValidationError(
            "Resource is public; no access request is required.",
            error_code="resource_public",
        )

    if version.publisher_sub == requester_sub:
        raise ConflictError("You already own this resource.", error_code="self_request")

    if requester_sub in (version.access_rights or []):
        raise ConflictError(
            "You already have access to this resource.",
            error_code="already_granted",
        )

    dup_stmt = select(AccessRequest).where(
        AccessRequest.resource_version_id == version_id,
        AccessRequest.requester_sub == requester_sub,
        AccessRequest.status == "pending",
    )
    existing = (await db.execute(dup_stmt)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            "You already have a pending request for this resource.",
            error_code="duplicate_request",
            details={"id": existing.id},
        )

    req = AccessRequest(
        resource_version_id=version_id,
        requester_sub=requester_sub,
        owner_sub=version.publisher_sub,
        status="pending",
        message=message,
        expires_at=_now() + timedelta(days=settings.access_request_expiry_days),
    )
    db.add(req)
    await db.flush()

    await notification_service.create_notification(
        db,
        user_sub=version.publisher_sub,
        type="access_requested",
        message=(
            f"User {requester_sub} requested access to "
            f"'{version.title}' ({version.id})."
        ),
        resource_version_id=version.id,
        related_id=str(req.id),
    )

    await db.commit()
    await db.refresh(req)
    return req


async def list_incoming(db: AsyncSession, owner_sub: str) -> list[AccessRequest]:
    stmt = (
        select(AccessRequest)
        .where(AccessRequest.owner_sub == owner_sub)
        .order_by(AccessRequest.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_outgoing(db: AsyncSession, requester_sub: str) -> list[AccessRequest]:
    stmt = (
        select(AccessRequest)
        .where(AccessRequest.requester_sub == requester_sub)
        .order_by(AccessRequest.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def _get_request(
    db: AsyncSession, request_id: int, owner_sub: str
) -> AccessRequest:
    req = await db.get(AccessRequest, request_id)
    if req is None:
        raise NotFoundError(
            f"No access request with id {request_id}.",
            error_code="request_not_found",
        )
    if req.owner_sub != owner_sub:
        raise ForbiddenError("Only the resource owner may act on this request.")
    return req


async def accept(db: AsyncSession, request_id: int, owner_sub: str) -> AccessRequest:
    req = await _get_request(db, request_id, owner_sub)
    if req.status != "pending":
        raise ConflictError(
            f"Request is already '{req.status}'.", error_code="invalid_status"
        )

    version = await get_version(db, req.resource_version_id, with_datasets=False)
    rights = list(version.access_rights or [])
    if req.requester_sub not in rights:
        rights.append(req.requester_sub)
    version.access_rights = rights
    req.status = "accepted"
    req.resolved_at = _now()

    await notification_service.create_notification(
        db,
        user_sub=req.requester_sub,
        type="access_accepted",
        message=f"Your access request for '{version.title}' was accepted.",
        resource_version_id=version.id,
        related_id=str(req.id),
    )

    await db.commit()
    await db.refresh(req)
    return req


async def reject(db: AsyncSession, request_id: int, owner_sub: str) -> AccessRequest:
    req = await _get_request(db, request_id, owner_sub)
    if req.status != "pending":
        raise ConflictError(
            f"Request is already '{req.status}'.", error_code="invalid_status"
        )
    req.status = "rejected"
    req.resolved_at = _now()

    await notification_service.create_notification(
        db,
        user_sub=req.requester_sub,
        type="access_rejected",
        message=f"Your access request {req.id} was rejected.",
        resource_version_id=req.resource_version_id,
        related_id=str(req.id),
    )
    await db.commit()
    await db.refresh(req)
    return req


async def revoke(db: AsyncSession, request_id: int, owner_sub: str) -> AccessRequest:
    req = await _get_request(db, request_id, owner_sub)
    version = await get_version(db, req.resource_version_id, with_datasets=False)
    rights = [s for s in (version.access_rights or []) if s != req.requester_sub]
    version.access_rights = rights
    req.status = "revoked"
    req.resolved_at = _now()

    await notification_service.create_notification(
        db,
        user_sub=req.requester_sub,
        type="access_revoked",
        message=f"Your access to '{version.title}' was revoked.",
        resource_version_id=version.id,
        related_id=str(req.id),
    )
    await db.commit()
    await db.refresh(req)
    return req


async def can_download(version: ResourceVersion, user_sub: str | None) -> bool:
    if not version.is_private:
        return True
    if user_sub is None:
        return False
    if version.publisher_sub == user_sub:
        return True
    return user_sub in (version.access_rights or [])


async def purge_expired() -> int:
    factory = get_session_factory()
    async with factory() as db:
        stmt = (
            delete(AccessRequest)
            .where(AccessRequest.status == "pending")
            .where(AccessRequest.expires_at < _now())
        )
        result = await db.execute(stmt)
        await db.commit()
        purged = int(result.rowcount or 0)
        if purged:
            logger.info("Purged %d expired access requests.", purged)
        return purged
