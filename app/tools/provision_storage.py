"""Idempotently provision the object storage bucket.

Usage::

    python -m app.tools.provision_storage            # create bucket if missing
    python -m app.tools.provision_storage --check    # report only, never create
    python -m app.tools.provision_storage --wait 60  # retry for up to 60s while
                                                     # storage is unreachable

Exit codes: 0 bucket is usable, 2 access denied, 3 unreachable/timeout,
4 bucket missing (``--check`` only).

This is the single place that creates buckets. The API itself never creates
buckets at request time; ``docker/entrypoint.sh`` runs this before starting
uvicorn when ``PROVISION_STORAGE=true``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

from app.config import settings
from app.services.object_storage_service import (
    BucketStatus,
    S3ObjectStorageService,
)

logger = logging.getLogger("app.tools.provision_storage")

_EXIT = {
    BucketStatus.OK: 0,
    BucketStatus.DENIED: 2,
    BucketStatus.UNREACHABLE: 3,
    BucketStatus.MISSING: 4,
}


async def _run(check_only: bool, wait_seconds: float) -> BucketStatus:
    service = S3ObjectStorageService()
    deadline = time.monotonic() + wait_seconds
    delay = 1.0
    while True:
        status = (
            await service.check_bucket() if check_only else await service.provision_bucket()
        )
        if status is not BucketStatus.UNREACHABLE or time.monotonic() >= deadline:
            return status
        logger.info(
            "Object storage at %s unreachable; retrying in %.0fs", service.endpoint, delay
        )
        await asyncio.sleep(delay)
        delay = min(delay * 2, 10.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="Only report bucket status; never create."
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="Retry while storage is unreachable, up to this many seconds.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    legacy = settings.legacy_storage_env_in_use
    if legacy:
        logger.warning(
            "Legacy storage variables in use (%s); rename to S3_* before the next release.",
            ", ".join(legacy),
        )

    status = asyncio.run(_run(args.check, args.wait))
    logger.info(
        "bucket=%s endpoint=%s status=%s", settings.s3_bucket, settings.s3_endpoint, status.value
    )
    return _EXIT[status]


if __name__ == "__main__":
    sys.exit(main())
