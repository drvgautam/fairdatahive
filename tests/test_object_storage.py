"""Unit tests for the S3 object storage boundary (no real S3 required)."""

from __future__ import annotations

import io
import logging
from contextlib import asynccontextmanager
from typing import Any

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.config import Settings
from app.core.exceptions import StorageError
from app.services import object_storage_service as oss
from app.services.object_storage_service import (
    BucketStatus,
    S3ObjectStorageService,
)

# --------------------------------------------------------------------------- helpers


def _client_error(code: str, op: str = "HeadBucket", http: int = 400) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": code}, "ResponseMetadata": {"HTTPStatusCode": http}},
        op,
    )


class FakeS3:
    """Minimal async S3 client double recording calls and raising on demand."""

    def __init__(self, **behaviour: Any) -> None:
        self.behaviour = behaviour
        self.calls: list[tuple[str, dict]] = []
        self.objects: dict[str, bytes] = dict(behaviour.pop("objects", {}))

    def _maybe_raise(self, op: str) -> None:
        exc = self.behaviour.get(op)
        if isinstance(exc, BaseException):
            raise exc

    async def head_bucket(self, **kw):
        self.calls.append(("head_bucket", kw))
        self._maybe_raise("head_bucket")
        return {}

    async def create_bucket(self, **kw):
        self.calls.append(("create_bucket", kw))
        self._maybe_raise("create_bucket")
        # After creation, head_bucket succeeds.
        self.behaviour.pop("head_bucket", None)
        return {}

    async def head_object(self, **kw):
        self.calls.append(("head_object", kw))
        self._maybe_raise("head_object")
        if kw["Key"] not in self.objects:
            raise _client_error("404", "HeadObject", 404)
        return {"ContentLength": len(self.objects[kw["Key"]]), "ETag": '"abc"'}

    async def delete_object(self, **kw):
        self.calls.append(("delete_object", kw))
        self._maybe_raise("delete_object")
        self.objects.pop(kw["Key"], None)
        return {}

    async def put_object(self, **kw):
        self.calls.append(("put_object", kw))
        self._maybe_raise("put_object")
        self.objects[kw["Key"]] = kw["Body"]
        return {}

    async def create_multipart_upload(self, **kw):
        self.calls.append(("create_multipart_upload", kw))
        self._maybe_raise("create_multipart_upload")
        return {"UploadId": "upl-1"}

    async def upload_part(self, **kw):
        self.calls.append(("upload_part", kw))
        self._maybe_raise("upload_part")
        return {"ETag": f'"part-{kw["PartNumber"]}"'}

    async def complete_multipart_upload(self, **kw):
        self.calls.append(("complete_multipart_upload", kw))
        self._maybe_raise("complete_multipart_upload")
        return {}

    async def abort_multipart_upload(self, **kw):
        self.calls.append(("abort_multipart_upload", kw))
        return {}

    def ops(self) -> list[str]:
        return [name for name, _ in self.calls]


class FakeSession:
    def __init__(self, client: FakeS3) -> None:
        self.fake = client
        self.client_kwargs: list[dict] = []

    def client(self, service_name: str, **kwargs):
        self.client_kwargs.append(kwargs)

        @asynccontextmanager
        async def _ctx():
            yield self.fake

        return _ctx()


class AsyncReader:
    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)

    async def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)


def _service(fake: FakeS3, **kw) -> S3ObjectStorageService:
    svc = S3ObjectStorageService(
        endpoint="http://storage:9000",
        public_endpoint="https://objects.example.org",
        access_key="app",
        secret_key="secret",
        bucket="bucket-under-test",
        region="us-east-1",
        **kw,
    )
    svc._session = FakeSession(fake)  # type: ignore[assignment]
    return svc


# ------------------------------------------------------------------- settings/aliases


def test_s3_settings_prefer_new_names_over_legacy(monkeypatch, caplog):
    for key in list(__import__("os").environ):
        if key.upper().startswith(("S3_", "MINIO_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("S3_ENDPOINT", "http://new:9000")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://old:9000")
    monkeypatch.setenv("MINIO_BUCKET", "legacy-bucket")
    monkeypatch.setenv("S3_SECRET_KEY", "new-secret")
    monkeypatch.setenv("MINIO_SECRET_KEY", "old-secret")

    with caplog.at_level(logging.WARNING, logger="app.config"):
        s = Settings(_env_file=None)

    assert s.s3_endpoint == "http://new:9000"
    assert s.s3_bucket == "legacy-bucket"  # legacy alone still honoured
    assert s.s3_secret_key == "new-secret"
    assert s.s3_addressing_style == "path"
    assert s.s3_public_url == "http://new:9000"
    assert sorted(s.legacy_storage_env_in_use) == [
        "MINIO_BUCKET",
        "MINIO_ENDPOINT",
        "MINIO_SECRET_KEY",
    ]

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("S3_ENDPOINT" in w and "MINIO_ENDPOINT" in w for w in warnings)
    assert any("S3_SECRET_KEY" in w for w in warnings)
    # Never log credential values.
    assert all("new-secret" not in w and "old-secret" not in w for w in warnings)
    # No warning for a legacy var that has no S3_ counterpart set.
    assert not any("MINIO_BUCKET" in w for w in warnings)


def test_s3_settings_legacy_only(monkeypatch):
    for key in list(__import__("os").environ):
        if key.upper().startswith(("S3_", "MINIO_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9002")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    s = Settings(_env_file=None)
    assert s.s3_endpoint == "http://minio:9000"
    assert s.s3_public_url == "http://localhost:9002"
    assert s.s3_access_key == "ak"


def test_client_uses_sigv4_and_path_style():
    fake = FakeS3()
    svc = _service(fake, addressing_style="path")
    svc._client()
    cfg = svc._session.client_kwargs[0]["config"]  # type: ignore[attr-defined]
    assert cfg.signature_version == "s3v4"
    assert cfg.s3 == {"addressing_style": "path"}
    assert svc._session.client_kwargs[0]["endpoint_url"] == "http://storage:9000"  # type: ignore[attr-defined]

    svc._client(svc.public_endpoint)
    assert svc._session.client_kwargs[1]["endpoint_url"] == "https://objects.example.org"  # type: ignore[attr-defined]


# ------------------------------------------------------------------ bucket lifecycle


@pytest.mark.parametrize(
    "exc, expected",
    [
        (None, BucketStatus.OK),
        (_client_error("404", http=404), BucketStatus.MISSING),
        (_client_error("NoSuchBucket", http=404), BucketStatus.MISSING),
        (_client_error("403", http=403), BucketStatus.DENIED),
        (_client_error("AccessDenied", http=403), BucketStatus.DENIED),
        (_client_error("InvalidAccessKeyId", http=403), BucketStatus.DENIED),
        (EndpointConnectionError(endpoint_url="http://storage:9000"), BucketStatus.UNREACHABLE),
        (_client_error("500", http=500), BucketStatus.UNREACHABLE),
    ],
)
async def test_check_bucket_classifies_errors(exc, expected):
    fake = FakeS3(head_bucket=exc)
    assert await _service(fake).check_bucket() is expected
    assert fake.ops() == ["head_bucket"]


async def test_provision_bucket_creates_when_missing():
    fake = FakeS3(head_bucket=_client_error("404", http=404))
    status = await _service(fake).provision_bucket()
    assert status is BucketStatus.OK
    assert fake.ops() == ["head_bucket", "create_bucket", "head_bucket"]
    assert fake.calls[1][1] == {"Bucket": "bucket-under-test"}


async def test_provision_bucket_is_idempotent_and_never_creates_when_present():
    fake = FakeS3()
    assert await _service(fake).provision_bucket() is BucketStatus.OK
    assert "create_bucket" not in fake.ops()


async def test_provision_bucket_reports_denied_instead_of_creating():
    fake = FakeS3(head_bucket=_client_error("AccessDenied", http=403))
    assert await _service(fake).provision_bucket() is BucketStatus.DENIED
    assert "create_bucket" not in fake.ops()


async def test_provision_bucket_denied_on_create():
    fake = FakeS3(
        head_bucket=_client_error("404", http=404),
        create_bucket=_client_error("AccessDenied", "CreateBucket", 403),
    )
    assert await _service(fake).provision_bucket() is BucketStatus.DENIED


# ------------------------------------------------------------------------- uploads


async def test_upload_stream_small_body_uses_single_put():
    fake = FakeS3()
    data = b"hello world"
    checksum, size = await _service(fake).upload_stream("k/small.txt", AsyncReader(data), "text/plain")
    assert size == len(data)
    assert checksum == __import__("hashlib").sha256(data).hexdigest()
    assert fake.ops() == ["put_object"]
    assert fake.calls[0][1]["ContentType"] == "text/plain"
    assert fake.objects["k/small.txt"] == data


async def test_upload_stream_zero_byte_uses_single_put_not_multipart():
    fake = FakeS3()
    checksum, size = await _service(fake).upload_stream("k/empty.bin", AsyncReader(b""))
    assert size == 0
    assert fake.ops() == ["put_object"]
    assert fake.calls[0][1]["Body"] == b""
    assert checksum == __import__("hashlib").sha256(b"").hexdigest()


async def test_upload_stream_large_body_uses_multipart(monkeypatch):
    monkeypatch.setattr(oss, "_CHUNK_SIZE", 4)
    monkeypatch.setattr(oss, "_PART_SIZE", 8)
    fake = FakeS3()
    data = b"0123456789abcdefXYZ"  # 19 bytes -> parts of 8, 8, 3
    checksum, size = await _service(fake).upload_stream("k/big.bin", AsyncReader(data))
    assert size == 19
    assert checksum == __import__("hashlib").sha256(data).hexdigest()
    ops = fake.ops()
    assert ops[0] == "create_multipart_upload"
    assert ops.count("upload_part") == 3
    assert ops[-1] == "complete_multipart_upload"
    bodies = [kw["Body"] for name, kw in fake.calls if name == "upload_part"]
    assert b"".join(bodies) == data
    assert [len(b) for b in bodies] == [8, 8, 3]
    complete = fake.calls[-1][1]
    assert [p["PartNumber"] for p in complete["MultipartUpload"]["Parts"]] == [1, 2, 3]


async def test_upload_stream_multipart_failure_aborts_and_raises_storage_error(monkeypatch):
    monkeypatch.setattr(oss, "_CHUNK_SIZE", 4)
    monkeypatch.setattr(oss, "_PART_SIZE", 8)
    fake = FakeS3(upload_part=_client_error("InternalError", "UploadPart", 500))
    with pytest.raises(StorageError) as excinfo:
        await _service(fake).upload_stream("k/big.bin", AsyncReader(b"x" * 20))
    assert "abort_multipart_upload" in fake.ops()
    assert excinfo.value.status_code == 503


async def test_upload_bytes_missing_bucket_is_actionable():
    fake = FakeS3(put_object=_client_error("NoSuchBucket", "PutObject", 404))
    with pytest.raises(StorageError) as excinfo:
        await _service(fake).upload_bytes("k", b"data")
    assert excinfo.value.error_code == "storage_bucket_missing"
    assert excinfo.value.details == {"bucket": "bucket-under-test"}


# ------------------------------------------------------------------------- deletes


async def test_delete_object_returns_true_when_deleted():
    fake = FakeS3(objects={"k": b"x"})
    assert await _service(fake).delete_object("k") is True
    assert fake.ops() == ["head_object", "delete_object"]
    assert "k" not in fake.objects


async def test_delete_object_returns_false_when_already_absent():
    fake = FakeS3()
    assert await _service(fake).delete_object("missing") is False
    assert fake.ops() == ["head_object"]


async def test_delete_object_raises_storage_error_instead_of_swallowing():
    fake = FakeS3(objects={"k": b"x"}, delete_object=_client_error("AccessDenied", "DeleteObject", 403))
    with pytest.raises(StorageError):
        await _service(fake).delete_object("k")


async def test_delete_object_unreachable_raises_storage_error():
    fake = FakeS3(head_object=EndpointConnectionError(endpoint_url="http://storage:9000"))
    with pytest.raises(StorageError):
        await _service(fake).delete_object("k")


# -------------------------------------------------------------------------- head


async def test_head_object_none_when_missing_and_info_when_present():
    fake = FakeS3(objects={"k": b"abcd"})
    svc = _service(fake)
    assert await svc.head_object("nope") is None
    info = await svc.head_object("k")
    assert info is not None and info.size == 4 and info.etag == "abc"
