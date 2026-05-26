"""Authorization for reading resource versions (metadata, RDF, FAIR, etc.)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.resource import Resource, ResourceVersion
from app.services.resource_service import get_resource, get_version, list_versions


def user_can_view_version(version: ResourceVersion, user_sub: str | None) -> bool:
    """Return whether the caller may read this version's metadata."""
    if version.state == "draft":
        return user_sub is not None and version.publisher_sub == user_sub

    if not version.is_private:
        return True

    if user_sub is None:
        return False
    if version.publisher_sub == user_sub:
        return True
    return user_sub in (version.access_rights or [])


async def get_version_if_viewable(
    db: AsyncSession,
    version_id: str,
    user_sub: str | None,
    *,
    with_datasets: bool = True,
) -> ResourceVersion:
    version = await get_version(db, version_id, with_datasets=with_datasets)
    if not user_can_view_version(version, user_sub):
        raise NotFoundError(
            f"No resource version with ID '{version_id}' exists.",
            error_code="resource_version_not_found",
        )
    return version


async def list_versions_if_viewable(
    db: AsyncSession,
    base_id: str,
    user_sub: str | None,
) -> list[ResourceVersion]:
    await get_resource(db, base_id)
    versions = await list_versions(db, base_id)
    visible = [v for v in versions if user_can_view_version(v, user_sub)]
    if not visible:
        raise NotFoundError(
            f"No resource with ID '{base_id}' exists.",
            error_code="resource_not_found",
        )
    return visible


async def resource_has_viewable_version(
    db: AsyncSession,
    resource: Resource,
    user_sub: str | None,
) -> bool:
    versions = await list_versions(db, resource.id)
    return any(user_can_view_version(v, user_sub) for v in versions)
