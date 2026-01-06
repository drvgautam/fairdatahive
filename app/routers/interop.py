from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db
from app.core.exceptions import ForbiddenError
from app.services import datacite_service, resource_service
from app.services.rdf_service import version_to_graph
from app.services.shacl_service import validate_dcat_ap

router = APIRouter(prefix="/resources", tags=["interop"])


@router.get("/{version_id}/dcat-ap-report")
async def dcat_ap_report(
    version_id: str, db: AsyncSession = Depends(get_db)
) -> Response:
    version = await resource_service.get_version(db, version_id)
    if version.dcat_ap_report:
        return Response(version.dcat_ap_report, media_type="text/turtle")
    graph = await version_to_graph(db, version)
    _, report = validate_dcat_ap(graph)
    return Response(report, media_type="text/turtle")


@router.post("/{version_id}/mint-doi")
async def mint_doi(
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    version = await resource_service.get_version(db, version_id)
    if version.publisher_sub != user.sub:
        raise ForbiddenError("Only the owner may mint a DOI for this resource.")
    doi = await datacite_service.mint_doi(version)
    version.doi = doi
    await db.commit()
    return {"doi": doi, "version_id": version.id}
