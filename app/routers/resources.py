from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db,
    get_optional_user,
)
from app.core.resource_access import (
    get_version_if_viewable,
    list_versions_if_viewable,
)
from app.core.exceptions import GoneError
from app.core.pagination import PageParams, get_page_params
from app.schemas.fair import FairScore
from app.schemas.pagination import PageModel
from app.schemas.resource import (
    NewVersionRequest,
    ResourceCreate,
    ResourceVersionPatch,
    ResourceVersionRead,
    ResourceVersionSummary,
)
from app.services import resource_service
from app.services.fair_service import compute_fair_score
from app.services.rdf_service import to_jsonld, to_turtle, version_to_graph

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post(
    "",
    response_model=ResourceVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource(
    payload: ResourceCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await resource_service.create_resource(db, payload, user.sub)


@router.get("", response_model=PageModel[ResourceVersionSummary])
async def list_resources(
    scope: str | None = None,
    params: PageParams = Depends(get_page_params),
    db: AsyncSession = Depends(get_db),
):
    items, total = await resource_service.list_published(
        db, scope=scope, page=params.page, size=params.size
    )
    return PageModel[ResourceVersionSummary](
        items=[ResourceVersionSummary.model_validate(v) for v in items],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.get(
    "/{base_id}/versions",
    response_model=list[ResourceVersionSummary],
)
async def list_versions(
    base_id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    versions = await list_versions_if_viewable(
        db, base_id, user.sub if user else None
    )
    return [ResourceVersionSummary.model_validate(v) for v in versions]


@router.get("/{base_id}/latest")
async def get_latest(
    base_id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    latest = await resource_service.get_latest(db, base_id)
    version = await get_version_if_viewable(
        db, latest.id, user.sub if user else None
    )
    return RedirectResponse(
        url=f"/api/v1/resources/{version.id}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.delete("/{base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    base_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await resource_service.delete_resource(db, base_id, user.sub)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{version_id}", response_model=ResourceVersionRead)
async def get_version(
    version_id: str,
    request: Request,
    user: CurrentUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    version = await get_version_if_viewable(
        db, version_id, user.sub if user else None
    )
    if version.data_deleted:
        body = ResourceVersionRead.model_validate(version).model_dump(mode="json")
        raise GoneError(
            "This resource has been deleted; only metadata remains.",
            error_code="resource_deleted",
            details={"tombstone": body},
        )

    accept = request.headers.get("accept", "").lower()
    if "text/turtle" in accept:
        graph = await version_to_graph(db, version)
        return Response(to_turtle(graph), media_type="text/turtle")
    if "application/ld+json" in accept:
        graph = await version_to_graph(db, version)
        return Response(to_jsonld(graph), media_type="application/ld+json")

    return version


@router.patch("/{version_id}", response_model=ResourceVersionRead)
async def patch_draft(
    version_id: str,
    payload: ResourceVersionPatch,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await resource_service.patch_draft(db, version_id, payload, user.sub)


@router.post("/{version_id}/publish", response_model=ResourceVersionRead)
async def publish(
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await resource_service.publish_resource(db, version_id, user.sub)


@router.post("/{version_id}/deprecate", response_model=ResourceVersionRead)
async def deprecate(
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await resource_service.deprecate_resource(db, version_id, user.sub)


@router.post(
    "/{base_id}/versions",
    response_model=ResourceVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_version(
    base_id: str,
    payload: NewVersionRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await resource_service.create_new_version(
        db, base_id, payload, user.sub
    )


@router.delete(
    "/{version_id}/version",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_version(
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await resource_service.delete_version(db, version_id, user.sub)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{version_id}/fair-score", response_model=FairScore)
async def fair_score(
    version_id: str,
    user: CurrentUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    version = await get_version_if_viewable(
        db, version_id, user.sub if user else None
    )
    return await compute_fair_score(db, version)
