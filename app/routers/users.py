from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.models.resource import Resource, ResourceVersion
from app.models.user import UserProfile
from app.schemas.resource import ResourceVersionSummary
from app.schemas.user import UserProfileRead, UserProfileUpdate

router = APIRouter(prefix="/users", tags=["users"])


async def _upsert_profile(db: AsyncSession, user: CurrentUser) -> UserProfile:
    profile = await db.get(UserProfile, user.sub)
    if profile is None:
        profile = UserProfile(
            sub=user.sub,
            display_name=user.display_name,
            email=user.email,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/me", response_model=UserProfileRead)
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    return await _upsert_profile(db, user)


@router.patch("/me", response_model=UserProfileRead)
async def update_me(
    payload: UserProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    profile = await _upsert_profile(db, user)
    if payload.display_name is not None:
        profile.display_name = payload.display_name
    if payload.email is not None:
        profile.email = payload.email
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/me/resources", response_model=list[ResourceVersionSummary])
async def list_my_resources(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResourceVersion]:
    stmt = (
        select(ResourceVersion)
        .join(Resource, Resource.id == ResourceVersion.base_resource_id)
        .where(Resource.owner_sub == user.sub)
        .order_by(ResourceVersion.issued.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


@router.get("/{sub}", response_model=UserProfileRead)
async def get_user(sub: str, db: AsyncSession = Depends(get_db)) -> UserProfile:
    profile = await db.get(UserProfile, sub)
    if profile is None:
        raise NotFoundError(
            f"User '{sub}' not found.", error_code="user_not_found"
        )
    return profile
