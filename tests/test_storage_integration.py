"""S3 compatibility tests against a real object store (RustFS by default).

These prove the S3 feature surface FairDataHive relies on against the exact
pinned build in ``docker-compose.yml``. They are skipped unless
``STORAGE_INTEGRATION_ENDPOINT`` is set, e.g.::

    docker compose up -d rustfs
    STORAGE_INTEGRATION_ENDPOINT=http://127.0.0.1:9002 \
    STORAGE_INTEGRATION_ACCESS_KEY=rustfsadmin \
    STORAGE_INTEGRATION_SECRET_KEY=rustfsadmin \
    pytest tests/test_storage_integration.py -m integration -v

or simply ``make test-storage``. Each run uses a fresh, uniquely named bucket
and deletes it afterwards.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio

from app.core.exceptions import StorageError
from app.services.object_storage_service import (
    BucketStatus,
    S3ObjectStorageService,
)

pytestmark = pytest.mark.integration

_ENDPOINT = os.environ.get("STORAGE_INTEGRATION_ENDPOINT")
_PUBLIC = os.environ.get("STORAGE_INTEGRATION_PUBLIC_ENDPOINT", _ENDPOINT)
_ACCESS = os.environ.get("STORAGE_INTEGRATION_ACCESS_KEY", "rustfsadmin")
_SECRET = os.environ.get("STORAGE_INTEGRATION_SECRET_KEY", "rustfsadmin")
_REGION = os.environ.get("STORAGE_INTEGRATION_REGION", "us-east-1")

if not _ENDPOINT:
    pytest.skip(
        "set STORAGE_INTEGRATION_ENDPOINT to run object storage integration tests",
        allow_module_level=True,
    )

_PART = 5 * 1024 * 1024


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)

    async def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)


@pytest_asyncio.fixture(scope="module")
async def storage():
    bucket = f"fdh-it-{uuid.uuid4().hex[:12]}"
    svc = S3ObjectStorageService(
        endpoint=_ENDPOINT,
        public_endpoint=_PUBLIC,
        access_key=_ACCESS,
        secret_key=_SECRET,
        bucket=bucket,
        region=_REGION,
        addressing_style="path",
    )
    assert await svc.check_bucket() is BucketStatus.MISSING
    assert await svc.provision_bucket() is BucketStatus.OK
    yield svc
    # Teardown: empty and remove the test bucket.
    async with svc._client() as s3:
        paginator = s3.get_paginator("list_objects_v2")
        async for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                await s3.delete_object(Bucket=bucket, Key=obj["Key"])
        uploads = await s3.list_multipart_uploads(Bucket=bucket)
        for up in uploads.get("Uploads", []):
            await s3.abort_multipart_upload(
                Bucket=bucket, Key=up["Key"], UploadId=up["UploadId"]
            )
        await s3.delete_bucket(Bucket=bucket)


# ------------------------------------------------------------------ bucket


async def test_provision_is_idempotent(storage):
    assert await storage.provision_bucket() is BucketStatus.OK
    assert await storage.check_bucket() is BucketStatus.OK


async def test_missing_bucket_is_classified_not_created():
    svc = S3ObjectStorageService(
        endpoint=_ENDPOINT,
        public_endpoint=_PUBLIC,
        access_key=_ACCESS,
        secret_key=_SECRET,
        bucket=f"fdh-never-{uuid.uuid4().hex[:8]}",
        region=_REGION,
    )
    assert await svc.check_bucket() is BucketStatus.MISSING
    with pytest.raises(StorageError) as excinfo:
        await svc.upload_bytes("k", b"x")
    assert excinfo.value.error_code == "storage_bucket_missing"
    assert await svc.check_bucket() is BucketStatus.MISSING


async def test_bad_credentials_are_denied_not_unreachable(storage):
    svc = S3ObjectStorageService(
        endpoint=_ENDPOINT,
        public_endpoint=_PUBLIC,
        access_key="not-a-real-key",
        secret_key="not-a-real-secret",
        bucket=storage.bucket,
        region=_REGION,
    )
    assert await svc.check_bucket() is BucketStatus.DENIED


# ----------------------------------------------------------------- objects


async def test_put_head_get_delete_roundtrip(storage):
    key = "public/resource-it/" + uuid.uuid4().hex[:8] + "-data.csv"
    body = b"a,b\n1,2\n"
    checksum, size = await storage.upload_bytes(key, body, "text/csv")
    assert size == len(body)
    assert checksum == hashlib.sha256(body).hexdigest()

    info = await storage.head_object(key)
    assert info is not None
    assert info.size == len(body)
    assert info.content_type == "text/csv"

    assert await storage.get_object_bytes(key) == body

    assert await storage.delete_object(key) is True
    assert await storage.head_object(key) is None
    assert await storage.delete_object(key) is False


async def test_user_metadata_is_preserved(storage):
    key = "meta/" + uuid.uuid4().hex
    async with storage._client() as s3:
        await s3.put_object(
            Bucket=storage.bucket,
            Key=key,
            Body=b"m",
            ContentType="application/octet-stream",
            # S3 user metadata is ASCII-only (botocore enforces this client-side),
            # so non-ASCII filenames must be stored in the DB, not in metadata.
            Metadata={"original-filename": "overview.csv", "sha256": "abc"},
        )
    info = await storage.head_object(key)
    assert info is not None
    assert info.metadata.get("sha256") == "abc"
    assert info.metadata.get("original-filename") == "overview.csv"


async def test_unicode_and_space_keys(storage):
    for name in ("données été.csv", "測試 文件.txt", "emoji-🧪.bin"):
        key = storage.make_object_key("public", "resource-unicode", name)
        assert key.endswith(name)
        await storage.upload_bytes(key, name.encode("utf-8"))
        assert await storage.get_object_bytes(key) == name.encode("utf-8")
        info = await storage.head_object(key)
        assert info is not None and info.size == len(name.encode("utf-8"))
        assert await storage.delete_object(key) is True


async def test_zero_byte_object(storage):
    key = "empty/" + uuid.uuid4().hex
    checksum, size = await storage.upload_stream(key, _Reader(b""), "text/plain")
    assert size == 0
    assert checksum == hashlib.sha256(b"").hexdigest()
    info = await storage.head_object(key)
    assert info is not None and info.size == 0
    assert await storage.get_object_bytes(key) == b""


async def test_multipart_upload_complete(storage):
    key = "big/" + uuid.uuid4().hex
    body = os.urandom(2 * _PART + 12345)  # 3 parts: 5 MiB, 5 MiB, tail
    checksum, size = await storage.upload_stream(key, _Reader(body), "application/octet-stream")
    assert size == len(body)
    assert checksum == hashlib.sha256(body).hexdigest()
    info = await storage.head_object(key)
    assert info is not None and info.size == len(body)
    downloaded = await storage.get_object_bytes(key)
    assert hashlib.sha256(downloaded).hexdigest() == checksum
    # A multipart ETag is not a content hash (documented in the migration plan).
    assert info.etag != checksum


async def test_multipart_abort_leaves_nothing_behind(storage):
    key = "abort/" + uuid.uuid4().hex
    async with storage._client() as s3:
        created = await s3.create_multipart_upload(Bucket=storage.bucket, Key=key)
        upload_id = created["UploadId"]
        await s3.upload_part(
            Bucket=storage.bucket, Key=key, UploadId=upload_id, PartNumber=1, Body=b"x" * 1024
        )
        await s3.abort_multipart_upload(Bucket=storage.bucket, Key=key, UploadId=upload_id)
        listing = await s3.list_multipart_uploads(Bucket=storage.bucket, Prefix="abort/")
        assert not [u for u in listing.get("Uploads", []) if u["UploadId"] == upload_id]
    assert await storage.head_object(key) is None


# ---------------------------------------------------------------- presign


async def test_presigned_get_via_public_endpoint(storage):
    key = "signed/" + uuid.uuid4().hex + "-report.txt"
    body = b"signed download"
    await storage.upload_bytes(key, body, "text/plain")

    url = await storage.presigned_url(key, expires_in=300)
    parsed = urlparse(url)
    assert url.startswith(_PUBLIC.rstrip("/"))
    assert f"/{storage.bucket}/" in parsed.path  # path-style addressing
    assert "X-Amz-Signature" in parse_qs(parsed.query)

    async with httpx.AsyncClient() as http:
        ok = await http.get(url)
        assert ok.status_code == 200
        assert ok.content == body

        # Tampered signature must be rejected.
        tampered = url[:-4] + ("0000" if not url.endswith("0000") else "1111")
        bad = await http.get(tampered)
        assert bad.status_code == 403

        # Unsigned access to a private bucket must be rejected.
        anon = await http.get(f"{_PUBLIC.rstrip('/')}/{storage.bucket}/{key}")
        assert anon.status_code in (401, 403)

        # Signed URL for a different key must not grant access to this key.
        other_url = await storage.presigned_url(key + ".other", expires_in=300)
        swapped = other_url.replace(key + ".other", key)
        assert (await http.get(swapped)).status_code == 403


async def test_presigned_url_expires(storage):
    key = "expiring/" + uuid.uuid4().hex
    await storage.upload_bytes(key, b"ttl")
    url = await storage.presigned_url(key, expires_in=1)
    await asyncio.sleep(3)
    async with httpx.AsyncClient() as http:
        resp = await http.get(url)
        assert resp.status_code == 403


async def test_range_read(storage):
    key = "range/" + uuid.uuid4().hex
    await storage.upload_bytes(key, b"0123456789")
    url = await storage.presigned_url(key, expires_in=60)
    async with httpx.AsyncClient() as http:
        resp = await http.get(url, headers={"Range": "bytes=2-5"})
        assert resp.status_code == 206
        assert resp.content == b"2345"
