from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.constants import LICENSE_VOCAB
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    PublishGuardError,
    ValidationError,
)
from app.models.dataset import DataService, Dataset, Distribution
from app.models.resource import Resource, ResourceVersion
from app.schemas.dataset import DatasetCreate, DistributionCreate
from app.schemas.resource import (
    NewVersionRequest,
    ResourceCreate,
    ResourceVersionPatch,
)

logger = logging.getLogger(__name__)


def version_relations_options():
    """Eager-load datasets, distributions, and data services for response serialization."""
    return (
        selectinload(ResourceVersion.datasets)
        .selectinload(Dataset.distributions)
        .selectinload(Distribution.data_service)
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_resource_id() -> str:
    return f"resource-{uuid.uuid4().hex[:12]}"


def make_version_id(base_id: str, when: datetime | None = None) -> str:
    when = when or _now()
    ts = (
        f"{when.year}-{when.month}-{when.day}-"
        f"{when.hour}-{when.minute}-{when.second}-{when.microsecond}"
    )
    return f"{base_id}-v-{ts}"


def make_dataset_id() -> str:
    return f"dataset-{uuid.uuid4().hex[:12]}"


def make_distribution_id() -> str:
    return f"dist-{uuid.uuid4().hex[:12]}"


def make_data_service_id() -> str:
    return f"svc-{uuid.uuid4().hex[:12]}"


async def get_resource(db: AsyncSession, resource_id: str) -> Resource:
    res = await db.get(Resource, resource_id)
    if res is None:
        raise NotFoundError(
            f"No resource with ID '{resource_id}' exists.",
            error_code="resource_not_found",
        )
    return res


async def get_version(
    db: AsyncSession, version_id: str, *, with_datasets: bool = True
) -> ResourceVersion:
    stmt = select(ResourceVersion).where(ResourceVersion.id == version_id)
    if with_datasets:
        stmt = stmt.options(version_relations_options())
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()
    if version is None:
        raise NotFoundError(
            f"No resource version with ID '{version_id}' exists.",
            error_code="resource_version_not_found",
        )
    return version


def _ensure_owner(version: ResourceVersion, user_sub: str) -> None:
    if version.publisher_sub != user_sub:
        raise ForbiddenError("Only the resource owner may perform this action.")


def _build_distribution(
    dataset: Dataset, payload: DistributionCreate
) -> Distribution:
    if payload.dist_type == "upload":
        if not payload.upload_token or not str(payload.upload_token).strip():
            raise ValidationError(
                "upload_token is required for distributions of type 'upload'. "
                "For ZIP uploads, register each extracted file using its upload_token "
                "from extracted_files—the archive container is not stored."
            )
        download_url = payload.upload_token
        access_url = None
    else:
        if not payload.access_url:
            raise ValidationError(
                f"access_url is required for distributions of type "
                f"'{payload.dist_type}'."
            )
        access_url = payload.access_url
        download_url = None

    dist = Distribution(
        id=make_distribution_id(),
        dataset_id=dataset.id,
        dist_type=payload.dist_type,
        title=payload.title,
        description=payload.description,
        access_url=access_url,
        download_url=download_url,
        media_type=payload.media_type,
        checksum_sha256=payload.checksum_sha256,
        byte_size=payload.byte_size,
    )
    if payload.data_service is not None:
        dist.data_service = DataService(
            id=make_data_service_id(),
            distribution_id=dist.id,
            endpoint_url=payload.data_service.endpoint_url,
            description=payload.data_service.description,
        )
    return dist


def _build_datasets_for_version(
    version_id: str, payloads: Iterable[DatasetCreate]
) -> list[Dataset]:
    out: list[Dataset] = []
    for ds_payload in payloads:
        ds = Dataset(id=make_dataset_id(), resource_version_id=version_id)
        for dist_payload in ds_payload.distributions:
            ds.distributions.append(_build_distribution(ds, dist_payload))
        out.append(ds)
    return out


async def create_resource(
    db: AsyncSession, payload: ResourceCreate, user_sub: str
) -> ResourceVersion:
    if payload.license_id is not None and payload.license_id not in LICENSE_VOCAB:
        raise ValidationError(
            f"Unknown license_id '{payload.license_id}'. "
            f"Choose one of: {', '.join(sorted(LICENSE_VOCAB.keys()))}."
        )

    base_id = make_resource_id()
    version_id = make_version_id(base_id)

    resource = Resource(
        id=base_id,
        scope=payload.scope,
        owner_sub=user_sub,
        current_version_id=None,
    )
    db.add(resource)

    version = ResourceVersion(
        id=version_id,
        base_resource_id=base_id,
        previous_version_id=None,
        title=payload.title,
        description=payload.description,
        state="draft",
        publisher_sub=user_sub,
        theme=payload.theme,
        keywords=list(payload.keywords) if payload.keywords else None,
        license_id=payload.license_id,
        doi=payload.doi,
        language=payload.language,
        provenance=payload.provenance,
        rights_statement=payload.rights_statement,
        spatial=payload.spatial,
        temporal=payload.temporal,
        assumptions=payload.assumptions,
        technique=payload.technique,
        post_processing=payload.post_processing,
        is_private=payload.is_private,
        access_rights=(
            list(set([user_sub, *payload.access_rights]))
            if payload.is_private
            else (list(payload.access_rights) if payload.access_rights else None)
        ),
    )
    db.add(version)

    for ds in _build_datasets_for_version(version_id, payload.datasets):
        version.datasets.append(ds)

    await db.flush()
    await db.commit()
    return await get_version(db, version_id)


async def patch_draft(
    db: AsyncSession,
    version_id: str,
    payload: ResourceVersionPatch,
    user_sub: str,
) -> ResourceVersion:
    version = await get_version(db, version_id)
    _ensure_owner(version, user_sub)
    if version.state != "draft":
        raise ConflictError(
            f"Cannot PATCH a resource in state '{version.state}'. Create a new "
            f"version instead.",
            error_code="resource_not_draft",
        )

    update = payload.model_dump(exclude_unset=True)
    if "license_id" in update and update["license_id"] is not None:
        if update["license_id"] not in LICENSE_VOCAB:
            raise ValidationError(
                f"Unknown license_id '{update['license_id']}'."
            )
    for key, value in update.items():
        setattr(version, key, value)
    if version.is_private:
        rights = set(version.access_rights or [])
        rights.add(version.publisher_sub)
        version.access_rights = sorted(rights)
    await db.commit()
    return await get_version(db, version_id)


async def _count_distributions(db: AsyncSession, version_id: str) -> int:
    stmt = (
        select(func.count(Distribution.id))
        .join(Dataset, Distribution.dataset_id == Dataset.id)
        .where(Dataset.resource_version_id == version_id)
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def evaluate_publish_guard(
    db: AsyncSession, version: ResourceVersion
) -> list[dict[str, Any]]:
    """Return a list of failing checks (empty if all pass)."""

    from app.services.fair_service import compute_fair_score

    failures: list[dict[str, Any]] = []

    if version.state != "draft":
        failures.append(
            {
                "check": "state",
                "message": f"Resource is in state '{version.state}', expected 'draft'.",
            }
        )

    if not version.license_id:
        failures.append(
            {
                "check": "license",
                "message": "license_id is required before publishing.",
            }
        )

    dist_count = await _count_distributions(db, version.id)
    if dist_count == 0:
        failures.append(
            {
                "check": "distribution",
                "message": "At least one Dataset with a Distribution must exist.",
            }
        )

    fair = await compute_fair_score(db, version)
    if fair.score < settings.fair_score_publish_threshold:
        failures.append(
            {
                "check": "fair_score",
                "message": (
                    f"FAIR score {fair.score:.2f} is below the publish threshold "
                    f"{settings.fair_score_publish_threshold:.2f}."
                ),
                "fair_score": fair.score,
                "suggestions": fair.suggestions,
            }
        )

    return failures


async def publish_resource(
    db: AsyncSession, version_id: str, user_sub: str
) -> ResourceVersion:
    version = await get_version(db, version_id)
    _ensure_owner(version, user_sub)

    failures = await evaluate_publish_guard(db, version)
    if failures:
        raise PublishGuardError(
            "Publish guard failed. Fix the following issues and retry.",
            details=failures,
        )

    version.state = "published"
    version.issued = _now()
    version.modified = _now()
    resource = await get_resource(db, version.base_resource_id)
    resource.current_version_id = version.id
    await db.commit()

    try:
        from app.services import embedding_service

        await embedding_service.schedule_embedding_update(version.id)
    except Exception as exc:  # pragma: no cover - embedding update is best-effort
        logger.warning("Failed to schedule embedding update for %s: %s", version.id, exc)

    try:
        from app.services import cache_service

        await cache_service.invalidate_scope(resource.scope)
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.debug("Cache invalidation failed: %s", exc)

    return await get_version(db, version_id)


async def deprecate_resource(
    db: AsyncSession, version_id: str, user_sub: str
) -> ResourceVersion:
    version = await get_version(db, version_id)
    _ensure_owner(version, user_sub)
    if version.state == "deprecated":
        return version
    if version.state == "draft":
        raise ConflictError(
            "Cannot deprecate a draft. Publish it first or delete the version.",
            error_code="cannot_deprecate_draft",
        )
    version.state = "deprecated"
    version.modified = _now()
    await db.commit()
    return await get_version(db, version_id)


async def create_new_version(
    db: AsyncSession, base_id: str, payload: NewVersionRequest, user_sub: str
) -> ResourceVersion:
    resource = await get_resource(db, base_id)
    if resource.owner_sub != user_sub:
        raise ForbiddenError("Only the resource owner can create new versions.")

    if resource.current_version_id is None:
        raise ConflictError(
            "Resource has no published current version; finish the draft first.",
            error_code="no_current_version",
        )
    current = await get_version(db, resource.current_version_id)

    new_id = make_version_id(base_id)

    update = payload.model_dump(exclude_unset=True)
    update.pop("datasets", None)

    version = ResourceVersion(
        id=new_id,
        base_resource_id=base_id,
        previous_version_id=current.id,
        title=update.get("title", current.title),
        description=update.get("description", current.description),
        state="draft",
        publisher_sub=user_sub,
        theme=update.get("theme", current.theme),
        keywords=update.get("keywords", current.keywords),
        license_id=update.get("license_id", current.license_id),
        doi=update.get("doi", current.doi),
        language=update.get("language", current.language),
        provenance=update.get("provenance", current.provenance),
        rights_statement=update.get("rights_statement", current.rights_statement),
        spatial=update.get("spatial", current.spatial),
        temporal=update.get("temporal", current.temporal),
        assumptions=update.get("assumptions", current.assumptions),
        technique=update.get("technique", current.technique),
        post_processing=update.get("post_processing", current.post_processing),
        is_private=update.get("is_private", current.is_private),
        access_rights=update.get("access_rights", current.access_rights),
    )
    db.add(version)

    for ds in _build_datasets_for_version(new_id, payload.datasets):
        version.datasets.append(ds)

    await db.flush()
    await db.commit()
    return await get_version(db, new_id)


async def list_versions(
    db: AsyncSession, base_id: str
) -> list[ResourceVersion]:
    await get_resource(db, base_id)
    stmt = (
        select(ResourceVersion)
        .where(ResourceVersion.base_resource_id == base_id)
        .order_by(ResourceVersion.issued.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_latest(db: AsyncSession, base_id: str) -> ResourceVersion:
    resource = await get_resource(db, base_id)
    if resource.current_version_id is None:
        raise NotFoundError(
            f"Resource '{base_id}' has no published version yet.",
            error_code="no_current_version",
        )
    return await get_version(db, resource.current_version_id)


async def list_published(
    db: AsyncSession,
    *,
    scope: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[ResourceVersion], int]:
    base = (
        select(ResourceVersion)
        .join(Resource, Resource.current_version_id == ResourceVersion.id)
        .where(ResourceVersion.state == "published")
    )
    if scope:
        base = base.where(Resource.scope == scope)

    total_stmt = select(func.count()).select_from(base.subquery())
    total = int((await db.execute(total_stmt)).scalar() or 0)

    items_stmt = (
        base.order_by(ResourceVersion.issued.desc())
        .offset((page - 1) * size)
        .limit(size)
        .options(version_relations_options())
    )
    items = list((await db.execute(items_stmt)).scalars().all())
    return items, total


async def delete_version(
    db: AsyncSession, version_id: str, user_sub: str
) -> None:
    version = await get_version(db, version_id)
    _ensure_owner(version, user_sub)

    if version.state == "draft":
        await db.delete(version)
        await db.commit()
        return

    await _tombstone_versions(db, [version])
    await db.commit()


async def delete_resource(
    db: AsyncSession, base_id: str, user_sub: str
) -> None:
    resource = await get_resource(db, base_id)
    if resource.owner_sub != user_sub:
        raise ForbiddenError("Only the resource owner may delete this resource.")

    stmt = select(ResourceVersion).where(ResourceVersion.base_resource_id == base_id)
    versions = list((await db.execute(stmt)).scalars().all())
    await _tombstone_versions(db, versions)
    await db.commit()


async def _tombstone_versions(
    db: AsyncSession, versions: list[ResourceVersion]
) -> None:
    from app.services.minio_service import get_minio_service

    minio = None
    try:
        minio = get_minio_service()
    except Exception:  # pragma: no cover - test env may not have MinIO
        minio = None

    for v in versions:
        v.data_deleted = True
        v.state = "deprecated"
        v.modified = _now()

        dist_stmt = (
            select(Distribution)
            .join(Dataset, Distribution.dataset_id == Dataset.id)
            .where(Dataset.resource_version_id == v.id)
        )
        dists = list((await db.execute(dist_stmt)).scalars().all())
        for d in dists:
            if d.dist_type == "upload" and d.download_url and minio is not None:
                try:
                    await minio.delete_object(d.download_url)
                except Exception as exc:  # pragma: no cover
                    logger.warning("delete %s failed: %s", d.download_url, exc)
            d.download_url = None
            d.access_url = None


async def assert_not_tombstone(version: ResourceVersion) -> None:
    if version.data_deleted:
        raise GoneError(
            "This resource has been deleted; only metadata remains.",
            error_code="resource_deleted",
        )
