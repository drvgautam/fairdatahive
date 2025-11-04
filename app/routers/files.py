from __future__ import annotations

import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db,
    get_optional_user,
)
from app.core.exceptions import (
    ForbiddenError,
    GoneError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.schemas.dataset import PresignedDownloadResponse, UploadResponse
from app.services import access_service, audit_service
from app.services.minio_service import (
    MinioService,
    get_minio_service,
    upload_and_maybe_extract,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])


def _to_response(result, original_filename: str) -> UploadResponse:
    return UploadResponse(
        upload_token=result.object_key,
        object_key=result.object_key,
        checksum_sha256=result.checksum_sha256,
        byte_size=result.byte_size,
        media_type=result.media_type,
        original_filename=original_filename,
        extracted_files=[
            UploadResponse(
                upload_token=e.object_key,
                object_key=e.object_key,
                checksum_sha256=e.checksum_sha256,
                byte_size=e.byte_size,
                media_type=e.media_type,
                original_filename=e.original_filename,
                extracted_files=[],
            )
            for e in result.extracted
        ],
    )


@router.post(
    "/files/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file: UploadFile = File(...),
    scope: str = "public",
    resource_id: str | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> UploadResponse:
    if not file.filename:
        raise ValidationError("Uploaded file must have a filename.")
    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValidationError(
            f"File exceeds {settings.max_upload_size_mb} MB limit.",
            error_code="file_too_large",
        )

    minio = get_minio_service()
    try:
        await minio.ensure_bucket()
    except Exception as exc:  # pragma: no cover - bucket creation best-effort
        logger.debug("ensure_bucket: %s", exc)

    target_resource = resource_id or f"draft-{user.sub[:8]}-{uuid.uuid4().hex[:8]}"
    result = await upload_and_maybe_extract(
        minio,
        scope=scope,
        resource_id=target_resource,
        file_bytes=data,
        filename=file.filename,
        media_type=file.content_type,
    )
    return _to_response(result, file.filename)


@router.get(
    "/distributions/{distribution_id}/download",
    response_model=PresignedDownloadResponse,
)
async def download_distribution(
    distribution_id: str,
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> PresignedDownloadResponse:
    ctx = await audit_service.load_distribution_context(db, distribution_id)
    if ctx is None:
        raise NotFoundError(
            f"Distribution '{distribution_id}' not found.",
            error_code="distribution_not_found",
        )
    distribution, version = ctx

    if version.data_deleted or not distribution.download_url:
        raise GoneError(
            "This distribution's data has been deleted.",
            error_code="distribution_deleted",
        )

    if distribution.dist_type != "upload":
        if not distribution.access_url and not distribution.download_url:
            raise NotFoundError(
                "No download URL is set for this distribution.",
                error_code="no_download_url",
            )

    if version.is_private:
        if user is None:
            raise UnauthorizedError(
                "This resource requires authentication to download.",
            )
        if not await access_service.can_download(version, user.sub):
            raise ForbiddenError(
                "You do not have download rights for this resource.",
            )

    if distribution.dist_type == "upload":
        minio = get_minio_service()
        try:
            url = await minio.presigned_url(distribution.download_url)
        except Exception as exc:
            logger.warning("presigned_url failed: %s", exc)
            raise NotFoundError(
                "Failed to generate download URL.",
                error_code="presign_failed",
            ) from exc
    else:
        url = distribution.access_url or distribution.download_url

    client = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    background.add_task(
        audit_service.log_download,
        distribution_id=distribution.id,
        resource_version_id=version.id,
        user_sub=user.sub if user else None,
        ip_address=client,
        user_agent=ua,
    )

    return PresignedDownloadResponse(
        download_url=url,
        expires_in=settings.presigned_url_expiry_seconds,
        object_key=distribution.download_url or "",
    )
