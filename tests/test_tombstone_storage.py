"""Tombstone behaviour when object deletion fails (keys retained for reconciliation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import StorageError
from app.models.dataset import Dataset, Distribution
from app.models.resource import Resource, ResourceVersion
from app.services import resource_service

pytestmark = pytest.mark.asyncio


async def _seed(db) -> tuple[ResourceVersion, Distribution, Distribution]:
    now = resource_service._now()
    base = Resource(id="resource-tomb", scope="public", owner_sub="u1", created_at=now)
    version = ResourceVersion(
        id="resource-tomb-v-1",
        base_resource_id=base.id,
        title="T",
        description="d" * 60,
        state="published",
        publisher_sub="u1",
        issued=now,
        modified=now,
        keywords=["a", "b"],
        access_rights=[],
    )
    ds = Dataset(id="ds-1", resource_version_id=version.id, created_at=now)
    ok = Distribution(
        id="dist-ok",
        dataset_id=ds.id,
        dist_type="upload",
        title="ok",
        download_url="public/resource-tomb/ok.csv",
        media_type="text/csv",
        issued=now,
    )
    bad = Distribution(
        id="dist-bad",
        dataset_id=ds.id,
        dist_type="upload",
        title="bad",
        download_url="public/resource-tomb/bad.csv",
        access_url="http://x/bad.csv",
        media_type="text/csv",
        issued=now,
    )
    db.add_all([base, version, ds, ok, bad])
    await db.flush()
    return version, ok, bad


async def test_tombstone_keeps_key_when_delete_fails(db, monkeypatch):
    version, ok, bad = await _seed(db)

    async def fake_delete(key: str) -> bool:
        if key.endswith("bad.csv"):
            raise StorageError("denied", details={"code": "AccessDenied"})
        return True

    storage = MagicMock()
    storage.delete_object = AsyncMock(side_effect=fake_delete)
    monkeypatch.setattr(
        "app.services.object_storage_service.get_object_storage_service",
        lambda: storage,
    )

    await resource_service._tombstone_versions(db, [version])

    assert version.data_deleted is True
    assert version.state == "deprecated"
    assert ok.download_url is None and ok.access_url is None
    # Failed delete: key retained so the orphan can be reconciled; never downloadable
    # because the version is data_deleted.
    assert bad.download_url == "public/resource-tomb/bad.csv"
    assert bad.access_url is None
    assert storage.delete_object.await_count == 2
