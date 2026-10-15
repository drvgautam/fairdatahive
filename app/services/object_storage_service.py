"""S3-compatible object storage service.

FairDataHive talks to any S3 API (RustFS, MinIO, AWS S3, Ceph RGW) through
aioboto3. The service keeps two client configurations:

* the **internal** endpoint used for all reads, writes, and deletes, and
* the **public** endpoint used *only* to sign download URLs, so that the
  signature is computed against the hostname the browser will actually hit.

Bucket provisioning is an explicit operational step (``provision_bucket``);
request handlers never create buckets.
"""

from __future__ import annotations

import asyncio
import enum
import hashlib
import io
import logging
import mimetypes
import os
import uuid
import zipfile
from dataclasses import dataclass
from typing import Any

try:
    import aioboto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - aioboto3 is optional for import-time
    aioboto3 = None  # type: ignore[assignment]
    BotoConfig = None  # type: ignore[assignment]

    class BotoCoreError(Exception):  # type: ignore[no-redef]
        pass

    class ClientError(Exception):  # type: ignore[no-redef]
        pass

from app.config import settings
from app.core.exceptions import StorageError, ValidationError

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024  # 1 MiB
_PART_SIZE = 5 * 1024 * 1024  # 5 MiB for multipart uploads
_MAX_ZIP_MEMBERS = 200

_MISSING_BUCKET_CODES = {"404", "NoSuchBucket", "NotFound"}
_DENIED_CODES = {"403", "AccessDenied", "Forbidden", "InvalidAccessKeyId",
                 "SignatureDoesNotMatch"}
_MISSING_KEY_CODES = {"404", "NoSuchKey", "NotFound"}


class BucketStatus(str, enum.Enum):
    """Outcome of a bucket access check (distinct causes need distinct actions)."""

    OK = "ok"
    MISSING = "missing"
    DENIED = "denied"
    UNREACHABLE = "unreachable"


@dataclass
class UploadResult:
    object_key: str
    checksum_sha256: str
    byte_size: int
    media_type: str | None
    original_filename: str
    extracted: list["UploadResult"]


@dataclass
class ObjectInfo:
    key: str
    size: int
    etag: str
    content_type: str | None
    metadata: dict[str, str]


def _client_error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None) or {}
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = str(error.get("Code", "") or "")
    if not code:
        status_code = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
        code = str(status_code or "")
    return code


class S3ObjectStorageService:
    def __init__(
        self,
        endpoint: str | None = None,
        public_endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str | None = None,
        addressing_style: str | None = None,
    ) -> None:
        self.endpoint = (endpoint or settings.s3_endpoint).rstrip("/")
        self.public_endpoint = (public_endpoint or settings.s3_public_url).rstrip("/")
        self.access_key = access_key or settings.s3_access_key
        self.secret_key = secret_key or settings.s3_secret_key
        self.bucket = bucket or settings.s3_bucket
        self.region = region or settings.s3_region
        self.addressing_style = addressing_style or settings.s3_addressing_style
        if aioboto3 is None:
            self._session = None
        else:
            self._session = aioboto3.Session()

    # ------------------------------------------------------------------ clients

    def _boto_config(self):
        return BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": self.addressing_style},
        )

    def _client(self, endpoint_url: str | None = None):
        if self._session is None:
            raise RuntimeError(
                "aioboto3 is not installed; object storage operations are unavailable."
            )
        return self._session.client(
            "s3",
            endpoint_url=endpoint_url or self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=self._boto_config(),
        )

    # --------------------------------------------------------- bucket lifecycle

    async def check_bucket(self) -> BucketStatus:
        """Classify bucket access without mutating anything.

        Never raises for the expected failure modes; callers decide how to react
        (e.g. the provisioning task creates a MISSING bucket, the health probe
        reports DENIED/UNREACHABLE as a failing component).
        """
        try:
            async with self._client() as s3:
                await s3.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            code = _client_error_code(exc)
            if code in _MISSING_BUCKET_CODES:
                return BucketStatus.MISSING
            if code in _DENIED_CODES:
                return BucketStatus.DENIED
            logger.warning("check_bucket %s: unexpected error code %s", self.bucket, code)
            return BucketStatus.UNREACHABLE
        except (BotoCoreError, OSError, asyncio.TimeoutError) as exc:
            logger.warning("check_bucket %s: %s", self.bucket, exc.__class__.__name__)
            return BucketStatus.UNREACHABLE
        return BucketStatus.OK

    async def provision_bucket(self) -> BucketStatus:
        """Idempotently create the bucket. Intended for the explicit provisioning
        step (entrypoint / ``python -m app.tools.provision_storage``), not for
        request handlers.

        Returns the final status. ``DENIED``/``UNREACHABLE`` are returned, not
        raised, so the caller can decide whether to abort startup.
        """
        current = await self.check_bucket()
        if current is not BucketStatus.MISSING:
            return current
        try:
            async with self._client() as s3:
                kwargs: dict[str, Any] = {"Bucket": self.bucket}
                if self.region and self.region != "us-east-1":
                    kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": self.region
                    }
                await s3.create_bucket(**kwargs)
        except ClientError as exc:
            code = _client_error_code(exc)
            if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                return await self.check_bucket()
            if code in _DENIED_CODES:
                return BucketStatus.DENIED
            logger.error("provision_bucket %s failed: %s", self.bucket, code)
            return BucketStatus.UNREACHABLE
        except (BotoCoreError, OSError, asyncio.TimeoutError) as exc:
            logger.error("provision_bucket %s: %s", self.bucket, exc.__class__.__name__)
            return BucketStatus.UNREACHABLE
        logger.info("Created bucket %s", self.bucket)
        return await self.check_bucket()

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def make_object_key(
        scope: str, resource_id: str, filename: str
    ) -> str:
        clean_name = os.path.basename(filename.replace("\\", "/")).lstrip("/")
        if not clean_name or clean_name in (".", ".."):
            clean_name = "upload.bin"
        return f"{scope}/{resource_id}/{uuid.uuid4().hex[:8]}-{clean_name}"

    @staticmethod
    def guess_media_type(filename: str) -> str | None:
        ctype, _ = mimetypes.guess_type(filename)
        return ctype

    def _wrap(
        self, exc: BaseException, action: str, object_key: str | None = None
    ) -> StorageError:
        code = (
            _client_error_code(exc)
            if isinstance(exc, ClientError)
            else exc.__class__.__name__
        )
        target = f" '{object_key}'" if object_key else ""
        logger.error("object storage %s%s failed: %s", action, target, code)
        if code in {"NoSuchBucket"}:
            return StorageError(
                "Object storage bucket is not provisioned.",
                error_code="storage_bucket_missing",
                details={"bucket": self.bucket},
            )
        return StorageError(
            f"Object storage {action} failed.",
            details={"code": code},
        )

    # ------------------------------------------------------------------ objects

    async def upload_stream(
        self,
        object_key: str,
        upload_file,
        media_type: str | None = None,
    ) -> tuple[str, int]:
        """Upload from an async file-like object, computing SHA-256 while streaming.

        Bodies smaller than one multipart part (including zero-byte files) are
        sent with a single ``PutObject``; larger bodies use multipart upload and
        are aborted on failure so no orphaned parts remain.

        Returns (checksum_hex, byte_size).
        """

        hasher = hashlib.sha256()
        total = 0
        content_type = media_type or "application/octet-stream"

        async def _read_chunk() -> bytes:
            nonlocal total
            chunk = await upload_file.read(_CHUNK_SIZE)
            if chunk:
                hasher.update(chunk)
                total += len(chunk)
            return chunk

        # Buffer up to one part before deciding between PUT and multipart.
        buffer = bytearray()
        eof = False
        while len(buffer) < _PART_SIZE:
            chunk = await _read_chunk()
            if not chunk:
                eof = True
                break
            buffer.extend(chunk)

        try:
            async with self._client() as s3:
                if eof:
                    await s3.put_object(
                        Bucket=self.bucket,
                        Key=object_key,
                        Body=bytes(buffer),
                        ContentType=content_type,
                    )
                    return hasher.hexdigest(), total

                create = await s3.create_multipart_upload(
                    Bucket=self.bucket, Key=object_key, ContentType=content_type
                )
                upload_id = create["UploadId"]
                parts: list[dict] = []
                try:
                    part_number = 1
                    while True:
                        if len(buffer) >= _PART_SIZE or (eof and buffer):
                            part = await s3.upload_part(
                                Bucket=self.bucket,
                                Key=object_key,
                                UploadId=upload_id,
                                PartNumber=part_number,
                                Body=bytes(buffer),
                            )
                            parts.append(
                                {"ETag": part["ETag"], "PartNumber": part_number}
                            )
                            part_number += 1
                            buffer = bytearray()
                        if eof:
                            break
                        chunk = await _read_chunk()
                        if not chunk:
                            eof = True
                            continue
                        buffer.extend(chunk)
                    await s3.complete_multipart_upload(
                        Bucket=self.bucket,
                        Key=object_key,
                        UploadId=upload_id,
                        MultipartUpload={"Parts": parts},
                    )
                except BaseException:
                    try:
                        await s3.abort_multipart_upload(
                            Bucket=self.bucket, Key=object_key, UploadId=upload_id
                        )
                    except Exception as abort_exc:  # pragma: no cover - best effort
                        logger.error(
                            "abort_multipart_upload %s failed: %s", object_key, abort_exc
                        )
                    raise
        except (ClientError, BotoCoreError, OSError) as exc:
            raise self._wrap(exc, "upload", object_key) from exc

        return hasher.hexdigest(), total

    async def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        media_type: str | None = None,
    ) -> tuple[str, int]:
        checksum = hashlib.sha256(data).hexdigest()
        try:
            async with self._client() as s3:
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=object_key,
                    Body=data,
                    ContentType=media_type or "application/octet-stream",
                )
        except (ClientError, BotoCoreError, OSError) as exc:
            raise self._wrap(exc, "upload", object_key) from exc
        return checksum, len(data)

    async def head_object(self, object_key: str) -> ObjectInfo | None:
        """Return object metadata, or ``None`` when the key does not exist."""
        try:
            async with self._client() as s3:
                head = await s3.head_object(Bucket=self.bucket, Key=object_key)
        except ClientError as exc:
            if _client_error_code(exc) in _MISSING_KEY_CODES:
                return None
            raise self._wrap(exc, "head", object_key) from exc
        except (BotoCoreError, OSError) as exc:
            raise self._wrap(exc, "head", object_key) from exc
        return ObjectInfo(
            key=object_key,
            size=int(head.get("ContentLength", 0)),
            etag=str(head.get("ETag", "")).strip('"'),
            content_type=head.get("ContentType"),
            metadata=dict(head.get("Metadata") or {}),
        )

    async def get_object_bytes(self, object_key: str) -> bytes:
        try:
            async with self._client() as s3:
                obj = await s3.get_object(Bucket=self.bucket, Key=object_key)
                async with obj["Body"] as body:
                    return await body.read()
        except (ClientError, BotoCoreError, OSError) as exc:
            raise self._wrap(exc, "download", object_key) from exc

    async def delete_object(self, object_key: str) -> bool:
        """Delete an object.

        Returns ``True`` when a delete request succeeded and ``False`` when the
        key was already absent. Raises :class:`StorageError` on any other
        failure so callers can retry or record the key for reconciliation
        instead of silently orphaning data.
        """
        try:
            async with self._client() as s3:
                # S3 DELETE is idempotent and returns 204 for missing keys on
                # most implementations; check first so callers learn the truth.
                try:
                    await s3.head_object(Bucket=self.bucket, Key=object_key)
                except ClientError as head_exc:
                    if _client_error_code(head_exc) in _MISSING_KEY_CODES:
                        return False
                    raise
                await s3.delete_object(Bucket=self.bucket, Key=object_key)
        except (ClientError, BotoCoreError, OSError) as exc:
            raise self._wrap(exc, "delete", object_key) from exc
        return True

    async def presigned_url(
        self,
        object_key: str,
        expires_in: int | None = None,
    ) -> str:
        """Sign a GET URL against the *public* endpoint.

        The hostname is part of the SigV4 signature, so the URL must be
        generated with its final public scheme/host rather than rewritten.
        """
        expires = expires_in or settings.presigned_url_expiry_seconds
        try:
            async with self._client(self.public_endpoint) as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": object_key},
                    ExpiresIn=expires,
                )
        except (ClientError, BotoCoreError, OSError) as exc:
            raise self._wrap(exc, "presign", object_key) from exc


def _is_zip(data: bytes, filename: str) -> bool:
    if filename.lower().endswith(".zip"):
        return True
    return data[:4] == b"PK\x03\x04"


def _safe_zip_member_name(raw: str) -> str:
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        raise ValidationError(
            "ZIP entry path is not allowed.",
            error_code="zip_invalid_path",
        )
    base = os.path.basename(normalized)
    if not base or base in (".", ".."):
        raise ValidationError(
            "ZIP entry path is not allowed.",
            error_code="zip_invalid_path",
        )
    return base


def _extract_zip_sync(data: bytes) -> list[tuple[str, bytes]]:
    max_uncompressed = settings.max_upload_size_mb * 1024 * 1024
    out: list[tuple[str, bytes]] = []
    total_uncompressed = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        file_infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(file_infos) > _MAX_ZIP_MEMBERS:
            raise ValidationError(
                f"ZIP archive exceeds {_MAX_ZIP_MEMBERS} file limit.",
                error_code="zip_too_many_files",
            )
        for info in file_infos:
            safe_name = _safe_zip_member_name(info.filename)
            with zf.open(info, "r") as fh:
                member_data = fh.read()
            total_uncompressed += len(member_data)
            if total_uncompressed > max_uncompressed:
                raise ValidationError(
                    f"Extracted ZIP contents exceed {settings.max_upload_size_mb} MB.",
                    error_code="zip_expanded_too_large",
                )
            out.append((safe_name, member_data))
    return out


async def upload_and_maybe_extract(
    service: S3ObjectStorageService,
    scope: str,
    resource_id: str,
    file_bytes: bytes,
    filename: str,
    media_type: str | None,
) -> UploadResult:
    """Synchronous bytes upload with optional ZIP extraction.

    Use for files we already have in memory (post-streaming).
    """

    if _is_zip(file_bytes, filename):
        loop = asyncio.get_running_loop()
        members = await loop.run_in_executor(None, _extract_zip_sync, file_bytes)
        if not members:
            raise ValidationError(
                "ZIP archive contains no files to extract.",
                error_code="zip_empty",
            )
        extracted: list[UploadResult] = []
        for member_name, member_data in members:
            mtype = service.guess_media_type(member_name) or "application/octet-stream"
            key = service.make_object_key(scope, resource_id, member_name)
            checksum, size = await service.upload_bytes(key, member_data, mtype)
            extracted.append(
                UploadResult(
                    object_key=key,
                    checksum_sha256=checksum,
                    byte_size=size,
                    media_type=mtype,
                    original_filename=member_name,
                    extracted=[],
                )
            )
        return UploadResult(
            object_key="",
            checksum_sha256=hashlib.sha256(file_bytes).hexdigest(),
            byte_size=len(file_bytes),
            media_type="application/zip",
            original_filename=filename,
            extracted=extracted,
        )

    mtype = media_type or service.guess_media_type(filename) or "application/octet-stream"
    key = service.make_object_key(scope, resource_id, filename)
    checksum, size = await service.upload_bytes(key, file_bytes, mtype)
    return UploadResult(
        object_key=key,
        checksum_sha256=checksum,
        byte_size=size,
        media_type=mtype,
        original_filename=filename,
        extracted=[],
    )


_default_service: S3ObjectStorageService | None = None


def get_object_storage_service() -> S3ObjectStorageService:
    global _default_service
    if _default_service is None:
        _default_service = S3ObjectStorageService()
    return _default_service


def reset_object_storage_service() -> None:
    global _default_service
    _default_service = None
