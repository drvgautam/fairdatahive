from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import mimetypes
import os
import uuid
import zipfile
from dataclasses import dataclass

try:
    import aioboto3
    from botocore.config import Config as BotoConfig
except ImportError:  # pragma: no cover - aioboto3 is optional for import-time
    aioboto3 = None  # type: ignore[assignment]
    BotoConfig = None  # type: ignore[assignment]

from app.config import settings
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024  # 1 MiB
_PART_SIZE = 5 * 1024 * 1024  # 5 MiB for multipart uploads
_MAX_ZIP_MEMBERS = 200


@dataclass
class UploadResult:
    object_key: str
    checksum_sha256: str
    byte_size: int
    media_type: str | None
    original_filename: str
    extracted: list["UploadResult"]


class MinioService:
    def __init__(
        self,
        endpoint: str | None = None,
        public_endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str | None = None,
    ) -> None:
        self.endpoint = (endpoint or settings.minio_endpoint).rstrip("/")
        self.public_endpoint = (
            public_endpoint or settings.minio_public_url
        ).rstrip("/")
        self.access_key = access_key or settings.minio_access_key
        self.secret_key = secret_key or settings.minio_secret_key
        self.bucket = bucket or settings.minio_bucket
        self.region = region or settings.minio_region
        if aioboto3 is None:
            self._session = None
        else:
            self._session = aioboto3.Session()

    def _client(self, endpoint_url: str | None = None):
        if self._session is None:
            raise RuntimeError(
                "aioboto3 is not installed; MinIO operations are unavailable."
            )
        return self._session.client(
            "s3",
            endpoint_url=endpoint_url or self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=BotoConfig(signature_version="s3v4"),
        )

    async def ensure_bucket(self) -> None:
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=self.bucket)
            except Exception:
                try:
                    await s3.create_bucket(Bucket=self.bucket)
                except Exception as exc:  # pragma: no cover - bucket may exist
                    logger.warning("ensure_bucket: %s", exc)

    @staticmethod
    def make_object_key(
        scope: str, resource_id: str, filename: str
    ) -> str:
        clean_name = os.path.basename(filename.replace("\\", "/")).lstrip("/")
        if not clean_name or clean_name in (".", ".."):
            clean_name = "upload.bin"
        return f"{scope}/{resource_id}/{uuid.uuid4().hex[:8]}-{clean_name}"

    async def upload_stream(
        self,
        object_key: str,
        upload_file,
        media_type: str | None = None,
    ) -> tuple[str, int]:
        """Upload file from an async file-like object, computing SHA-256 streaming.

        Returns (checksum_hex, byte_size).
        """

        hasher = hashlib.sha256()
        total = 0

        async with self._client() as s3:
            create = await s3.create_multipart_upload(
                Bucket=self.bucket,
                Key=object_key,
                ContentType=media_type or "application/octet-stream",
            )
            upload_id = create["UploadId"]
            parts: list[dict] = []
            try:
                part_number = 1
                buffer = bytearray()
                while True:
                    chunk = await upload_file.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    total += len(chunk)
                    buffer.extend(chunk)
                    if len(buffer) >= _PART_SIZE:
                        part = await s3.upload_part(
                            Bucket=self.bucket,
                            Key=object_key,
                            UploadId=upload_id,
                            PartNumber=part_number,
                            Body=bytes(buffer),
                        )
                        parts.append({"ETag": part["ETag"], "PartNumber": part_number})
                        part_number += 1
                        buffer = bytearray()
                if buffer or part_number == 1:
                    part = await s3.upload_part(
                        Bucket=self.bucket,
                        Key=object_key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=bytes(buffer),
                    )
                    parts.append({"ETag": part["ETag"], "PartNumber": part_number})
                await s3.complete_multipart_upload(
                    Bucket=self.bucket,
                    Key=object_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
            except Exception:
                await s3.abort_multipart_upload(
                    Bucket=self.bucket, Key=object_key, UploadId=upload_id
                )
                raise

        return hasher.hexdigest(), total

    async def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        media_type: str | None = None,
    ) -> tuple[str, int]:
        checksum = hashlib.sha256(data).hexdigest()
        async with self._client() as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=data,
                ContentType=media_type or "application/octet-stream",
            )
        return checksum, len(data)

    async def delete_object(self, object_key: str) -> None:
        async with self._client() as s3:
            try:
                await s3.delete_object(Bucket=self.bucket, Key=object_key)
            except Exception as exc:  # pragma: no cover
                logger.warning("delete_object %s: %s", object_key, exc)

    async def presigned_url(
        self,
        object_key: str,
        expires_in: int | None = None,
    ) -> str:
        expires = expires_in or settings.presigned_url_expiry_seconds
        async with self._client(self.public_endpoint) as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=expires,
            )

    @staticmethod
    def guess_media_type(filename: str) -> str | None:
        ctype, _ = mimetypes.guess_type(filename)
        return ctype


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
    service: MinioService,
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


_default_service: MinioService | None = None


def get_minio_service() -> MinioService:
    global _default_service
    if _default_service is None:
        _default_service = MinioService()
    return _default_service


def reset_minio_service() -> None:
    global _default_service
    _default_service = None
