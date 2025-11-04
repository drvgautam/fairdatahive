from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.services.minio_service import upload_and_maybe_extract

pytestmark = pytest.mark.asyncio


def _zip_bytes(*members: tuple[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members:
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def minio_stub() -> MagicMock:
    service = MagicMock()
    service.guess_media_type = MagicMock(
        side_effect=lambda name: "text/csv" if name.endswith(".csv") else None
    )
    service.make_object_key = MagicMock(
        side_effect=lambda scope, rid, name: f"{scope}/{rid}/{name}"
    )
    service.upload_bytes = AsyncMock(return_value=("c" * 64, 12))
    return service


async def test_zip_upload_extracts_members(minio_stub: MagicMock) -> None:
    data = _zip_bytes(("a.csv", b"1,2,3"), ("b.csv", b"4,5,6"))
    result = await upload_and_maybe_extract(
        minio_stub,
        scope="public",
        resource_id="draft-1",
        file_bytes=data,
        filename="bundle.zip",
        media_type="application/zip",
    )

    assert result.object_key == ""
    assert len(result.extracted) == 2
    assert result.extracted[0].object_key == "public/draft-1/a.csv"
    assert minio_stub.upload_bytes.await_count == 2


async def test_zip_upload_rejects_empty_archive(minio_stub: MagicMock) -> None:
    data = _zip_bytes()
    with pytest.raises(ValidationError, match="no files"):
        await upload_and_maybe_extract(
            minio_stub,
            scope="public",
            resource_id="draft-1",
            file_bytes=data,
            filename="empty.zip",
            media_type="application/zip",
        )
    minio_stub.upload_bytes.assert_not_called()
