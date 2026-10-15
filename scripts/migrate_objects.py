#!/usr/bin/env python3
"""S3-to-S3 object copy with a durable JSONL manifest.

Used for MinIO → RustFS (or any S3 pair). Credentials come from the
environment so they never appear in command logs.

    SRC_S3_ENDPOINT=http://127.0.0.1:9000 \\
    SRC_S3_ACCESS_KEY=... SRC_S3_SECRET_KEY=... \\
    DST_S3_ENDPOINT=http://127.0.0.1:9002 \\
    DST_S3_ACCESS_KEY=... DST_S3_SECRET_KEY=... \\
    python scripts/migrate_objects.py inventory --manifest var/migrate-manifest.jsonl

    python scripts/migrate_objects.py copy --manifest var/migrate-manifest.jsonl
    python scripts/migrate_objects.py verify --manifest var/migrate-manifest.jsonl
    python scripts/migrate_objects.py db-check --manifest var/migrate-manifest.jsonl

Never point a RustFS volume at an existing MinIO data directory — copy through
the two S3 APIs instead. See docs/storage-migration.md.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import aioboto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError as exc:  # pragma: no cover
    raise SystemExit("aioboto3 is required: pip install -r requirements.txt") from exc

logger = logging.getLogger("migrate_objects")

_HASH_CHUNK = 1024 * 1024


@dataclass
class ManifestRow:
    bucket: str
    key: str
    size: int | None = None
    content_type: str | None = None
    etag: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    sha256: str | None = None
    copied: bool = False
    verified: bool = False
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, line: str) -> "ManifestRow":
        data = json.loads(line)
        data.setdefault("metadata", {})
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def load_manifest(path: Path) -> list[ManifestRow]:
    if not path.exists():
        return []
    rows: list[ManifestRow] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(ManifestRow.from_json(raw))
    return rows


def write_manifest(path: Path, rows: Iterable[ManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(row.to_json() + "\n")
    tmp.replace(path)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"missing required environment variable {name}")
    return value


def _client_kwargs(prefix: str) -> dict[str, Any]:
    style = os.environ.get(f"{prefix}_S3_ADDRESSING_STYLE", "path")
    return {
        "endpoint_url": _require_env(f"{prefix}_S3_ENDPOINT").rstrip("/"),
        "aws_access_key_id": _require_env(f"{prefix}_S3_ACCESS_KEY"),
        "aws_secret_access_key": _require_env(f"{prefix}_S3_SECRET_KEY"),
        "region_name": os.environ.get(f"{prefix}_S3_REGION", "us-east-1"),
        "config": BotoConfig(signature_version="s3v4", s3={"addressing_style": style}),
    }


def _bucket(prefix: str, fallback: str | None = None) -> str:
    return os.environ.get(f"{prefix}_S3_BUCKET") or fallback or os.environ.get(
        "S3_BUCKET", "fairdatahive-catalog"
    )


async def _sha256_object(s3, bucket: str, key: str) -> str:
    obj = await s3.get_object(Bucket=bucket, Key=key)
    hasher = hashlib.sha256()
    async with obj["Body"] as body:
        while True:
            chunk = await body.read(_HASH_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


async def inventory(args: argparse.Namespace) -> int:
    session = aioboto3.Session()
    bucket = _bucket("SRC")
    rows: list[ManifestRow] = []
    async with session.client("s3", **_client_kwargs("SRC")) as s3:
        paginator = s3.get_paginator("list_objects_v2")
        async for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                head = await s3.head_object(Bucket=bucket, Key=key)
                sha = None
                if args.hash:
                    sha = await _sha256_object(s3, bucket, key)
                rows.append(
                    ManifestRow(
                        bucket=bucket,
                        key=key,
                        size=int(obj.get("Size", 0)),
                        content_type=head.get("ContentType"),
                        etag=str(head.get("ETag", "")).strip('"'),
                        metadata=dict(head.get("Metadata") or {}),
                        sha256=sha,
                    )
                )
    write_manifest(args.manifest, rows)
    logger.info("inventoried %d objects into %s", len(rows), args.manifest)
    if not rows:
        logger.info(
            "Source bucket is empty — treat this as a fresh provision, not a data migration."
        )
    return 0


async def copy_objects(args: argparse.Namespace) -> int:
    rows = load_manifest(args.manifest)
    if not rows:
        logger.error("manifest %s is empty; run inventory first", args.manifest)
        return 2
    session = aioboto3.Session()
    src_bucket = _bucket("SRC", rows[0].bucket)
    dst_bucket = _bucket("DST", src_bucket)
    sem = asyncio.Semaphore(max(1, args.concurrency))
    failures = 0

    async with session.client("s3", **_client_kwargs("SRC")) as src, session.client(
        "s3", **_client_kwargs("DST")
    ) as dst:
        try:
            await dst.head_bucket(Bucket=dst_bucket)
        except ClientError:
            await dst.create_bucket(Bucket=dst_bucket)

        async def _one(row: ManifestRow) -> None:
            nonlocal failures
            if row.copied and not args.force:
                return
            async with sem:
                for attempt in range(1, args.retries + 2):
                    try:
                        obj = await src.get_object(Bucket=src_bucket, Key=row.key)
                        body = await obj["Body"].read()
                        put_kwargs: dict[str, Any] = {
                            "Bucket": dst_bucket,
                            "Key": row.key,
                            "Body": body,
                        }
                        if row.content_type:
                            put_kwargs["ContentType"] = row.content_type
                        if row.metadata:
                            put_kwargs["Metadata"] = row.metadata
                        await dst.put_object(**put_kwargs)
                        if row.size is not None and len(body) != row.size:
                            raise RuntimeError(
                                f"size mismatch after copy: {len(body)} != {row.size}"
                            )
                        if row.sha256 is None:
                            row.sha256 = hashlib.sha256(body).hexdigest()
                        elif hashlib.sha256(body).hexdigest() != row.sha256:
                            raise RuntimeError("sha256 mismatch after copy")
                        row.copied = True
                        row.error = None
                        return
                    except (ClientError, BotoCoreError, OSError, RuntimeError) as exc:
                        row.error = exc.__class__.__name__
                        logger.warning(
                            "copy %s attempt %d/%d failed: %s",
                            row.key,
                            attempt,
                            args.retries + 1,
                            exc.__class__.__name__,
                        )
                        await asyncio.sleep(min(2 ** (attempt - 1), 8))
                failures += 1

        await asyncio.gather(*(_one(row) for row in rows))

    write_manifest(args.manifest, rows)
    copied = sum(1 for r in rows if r.copied)
    logger.info("copied %d/%d objects (%d failures)", copied, len(rows), failures)
    return 1 if failures else 0


async def verify(args: argparse.Namespace) -> int:
    rows = load_manifest(args.manifest)
    if not rows:
        logger.error("manifest %s is empty; run inventory first", args.manifest)
        return 2
    session = aioboto3.Session()
    src_bucket = _bucket("SRC", rows[0].bucket)
    dst_bucket = _bucket("DST", src_bucket)
    failures = 0
    async with session.client("s3", **_client_kwargs("SRC")) as src, session.client(
        "s3", **_client_kwargs("DST")
    ) as dst:
        for row in rows:
            try:
                src_head = await src.head_object(Bucket=src_bucket, Key=row.key)
                dst_head = await dst.head_object(Bucket=dst_bucket, Key=row.key)
                src_size = int(src_head.get("ContentLength", 0))
                dst_size = int(dst_head.get("ContentLength", 0))
                if src_size != dst_size:
                    raise RuntimeError(f"size {src_size} != {dst_size}")
                src_sha = row.sha256 or await _sha256_object(src, src_bucket, row.key)
                dst_sha = await _sha256_object(dst, dst_bucket, row.key)
                if src_sha != dst_sha:
                    raise RuntimeError("sha256 mismatch")
                row.sha256 = src_sha
                row.size = src_size
                row.verified = True
                row.error = None
            except (ClientError, BotoCoreError, OSError, RuntimeError) as exc:
                row.verified = False
                row.error = str(exc)
                failures += 1
                logger.error("verify %s: %s", row.key, exc)
    write_manifest(args.manifest, rows)
    logger.info(
        "verified %d/%d objects (%d failures)",
        sum(1 for r in rows if r.verified),
        len(rows),
        failures,
    )
    return 1 if failures else 0


def _sqlite_or_async_url(url: str) -> str:
    """Use a sync driver for the lightweight db-check query."""
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("sqlite+aiosqlite://", "sqlite://")
    )


def db_check(args: argparse.Namespace) -> int:
    """Compare Distribution.download_url keys (upload type) to the manifest."""
    try:
        from sqlalchemy import create_engine, text
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("sqlalchemy is required for db-check") from exc

    url = args.database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("set --database-url or DATABASE_URL")
    rows = load_manifest(args.manifest)
    keys = {r.key for r in rows}
    engine = create_engine(_sqlite_or_async_url(url))
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT download_url
                FROM distribution
                WHERE dist_type = 'upload' AND download_url IS NOT NULL
                """
            )
        )
        db_keys = {row[0] for row in result}
    missing = sorted(db_keys - keys)
    orphans = sorted(keys - db_keys)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_objects": len(keys),
        "database_upload_keys": len(db_keys),
        "missing_from_storage": missing,
        "orphans_not_in_database": orphans,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "db-check: %d db keys, %d missing, %d orphans → %s",
        len(db_keys),
        len(missing),
        len(orphans),
        args.report,
    )
    if missing:
        logger.error("cutover is blocked: %d database keys are not in storage", len(missing))
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("var/migrate-manifest.jsonl"),
        help="Durable JSONL completion manifest (default: var/migrate-manifest.jsonl)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inv = sub.add_parser("inventory", help="List source objects into the manifest")
    inv.add_argument(
        "--hash",
        action="store_true",
        help="Compute SHA-256 for each source object (slower, recommended before cutover)",
    )

    copy_p = sub.add_parser("copy", help="Copy listed objects to the destination")
    copy_p.add_argument("--concurrency", type=int, default=4)
    copy_p.add_argument("--retries", type=int, default=3)
    copy_p.add_argument(
        "--force", action="store_true", help="Recopy keys already marked copied"
    )

    sub.add_parser("verify", help="Compare size and SHA-256 on both sides")

    dbp = sub.add_parser("db-check", help="Cross-check upload keys stored in PostgreSQL")
    dbp.add_argument("--database-url", default=None)
    dbp.add_argument(
        "--report",
        type=Path,
        default=Path("var/migrate-db-report.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "inventory":
        return asyncio.run(inventory(args))
    if args.command == "copy":
        return asyncio.run(copy_objects(args))
    if args.command == "verify":
        return asyncio.run(verify(args))
    if args.command == "db-check":
        return db_check(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
