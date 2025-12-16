from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_factory
from app.models.audit import DownloadLog
from app.models.dataset import Dataset, Distribution
from app.models.resource import ResourceVersion
from app.schemas.user import DownloadStats

logger = logging.getLogger(__name__)


async def log_download(
    *,
    distribution_id: str,
    resource_version_id: str,
    user_sub: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    factory = get_session_factory()
    try:
        async with factory() as db:
            entry = DownloadLog(
                distribution_id=distribution_id,
                resource_version_id=resource_version_id,
                user_sub=user_sub,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(entry)
            version = await db.get(ResourceVersion, resource_version_id)
            if version is not None:
                version.download_count = (version.download_count or 0) + 1
            await db.commit()
    except Exception as exc:  # pragma: no cover - audit failures must not bubble
        logger.warning("log_download failed: %s", exc)


async def stats_for_resource(
    db: AsyncSession, base_resource_id: str
) -> DownloadStats:
    base_q = (
        select(DownloadLog)
        .join(ResourceVersion, ResourceVersion.id == DownloadLog.resource_version_id)
        .where(ResourceVersion.base_resource_id == base_resource_id)
    )

    total_stmt = select(func.count()).select_from(base_q.subquery())
    total = int((await db.execute(total_stmt)).scalar() or 0)

    unique_stmt = (
        select(func.count(func.distinct(DownloadLog.user_sub)))
        .join(ResourceVersion, ResourceVersion.id == DownloadLog.resource_version_id)
        .where(ResourceVersion.base_resource_id == base_resource_id)
        .where(DownloadLog.user_sub.is_not(None))
    )
    unique = int((await db.execute(unique_stmt)).scalar() or 0)

    per_version_stmt = (
        select(DownloadLog.resource_version_id, func.count())
        .join(ResourceVersion, ResourceVersion.id == DownloadLog.resource_version_id)
        .where(ResourceVersion.base_resource_id == base_resource_id)
        .group_by(DownloadLog.resource_version_id)
    )
    per_version = {
        row[0]: int(row[1])
        for row in (await db.execute(per_version_stmt)).all()
    }

    rows_stmt = (
        select(DownloadLog.downloaded_at)
        .join(ResourceVersion, ResourceVersion.id == DownloadLog.resource_version_id)
        .where(ResourceVersion.base_resource_id == base_resource_id)
    )
    rows = list((await db.execute(rows_stmt)).all())
    per_month: dict[str, int] = defaultdict(int)
    for (ts,) in rows:
        if isinstance(ts, datetime):
            key = f"{ts.year}-{ts.month:02d}"
            per_month[key] += 1

    return DownloadStats(
        total_downloads=total,
        unique_downloaders=unique,
        downloads_by_version=per_version,
        downloads_by_month=dict(per_month),
    )


async def list_downloads(
    db: AsyncSession, version_id: str, *, limit: int = 100
) -> list[DownloadLog]:
    stmt = (
        select(DownloadLog)
        .where(DownloadLog.resource_version_id == version_id)
        .order_by(DownloadLog.downloaded_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def load_distribution_context(
    db: AsyncSession, distribution_id: str
) -> tuple[Distribution, ResourceVersion] | None:
    stmt = (
        select(Distribution, ResourceVersion)
        .join(Dataset, Dataset.id == Distribution.dataset_id)
        .join(ResourceVersion, ResourceVersion.id == Dataset.resource_version_id)
        .where(Distribution.id == distribution_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    return row[0], row[1]
