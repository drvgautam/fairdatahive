# Object storage migration (MinIO → RustFS)

This runbook is the operational half of the storage cutover. Application code already
talks S3 via `S3ObjectStorageService`. Compose now runs a **pinned** RustFS image on a
**new** `rustfs-data` volume. Never mount `minio-data` into RustFS — disk formats are
not portable.

If the source bucket is empty, skip copy/verify and treat the change as a
**fresh provision**. Still run the upload/download smoke checks and a backup-restore
drill before calling the environment ready.

## Prerequisites

- Access to the live MinIO endpoint and PostgreSQL.
- Enough disk for a second full copy plus backups.
- The pinned RustFS digest recorded in `docker-compose.yml` (override only with
  `RUSTFS_IMAGE` after re-running `make test-storage`).
- An agreed mutation freeze and rollback window (default: 14 days, MinIO left
  isolated and read-only).
- Do **not** run `docker compose down -v` during migration.

Versioning, lifecycle, encryption, Object Lock, and IAM are **not** assumed.
If the live MinIO uses any of those, stop and handle them as a separate project.

## Feature surface already proven

`make test-storage` exercises PUT/HEAD/GET/DELETE, metadata, Unicode keys,
zero-byte objects, multipart complete/abort, and signed GET (expiry, tamper,
unauthorized) against the pinned image.

## Fresh provision (no objects)

1. Copy `.env.example` → `.env` (or rename `MINIO_*` to `S3_*` and point
   `S3_ENDPOINT` at `http://rustfs:9000`).
2. `docker compose up -d`
3. Confirm `/api/v1/health` and `/api/v1/health/ready` report `storage: ok`.
4. Upload a file, download via a fresh presigned URL, delete a draft, confirm
   tombstone still returns 410.
5. Back up `rustfs-data` and restore it onto a throwaway volume once.
6. Record “fresh provision — no object migration” in the change ticket.

## Data migration

Credentials stay in the environment. Do not paste keys into command history.

### 1. Inventory and backup

1. Record bucket, object count, bytes, encryption, versioning, incomplete
   multiparts. Inspect the **running** MinIO, not this repository.
2. Backup PostgreSQL and the MinIO volume. Test a restore. Keep the old
   `quay.io/minio/minio:RELEASE.2024-04-18T19-09-19Z` digest and compose snippet.
3. Export the object list (hash recommended before any production cutover):

```bash
mkdir -p var
SRC_S3_ENDPOINT=http://127.0.0.1:9000 \
SRC_S3_ACCESS_KEY=... SRC_S3_SECRET_KEY=... \
SRC_S3_BUCKET=fairdatahive-catalog \
python scripts/migrate_objects.py inventory --hash --manifest var/migrate-manifest.jsonl
```

4. Cross-check catalog keys (upload distributions only; external URLs are not copied):

```bash
DATABASE_URL=postgresql://fairdatahive:fairdatahive@127.0.0.1:5434/fairdatahive \
python scripts/migrate_objects.py db-check --manifest var/migrate-manifest.jsonl
```

Missing keys block cutover. Orphans are recorded in `var/migrate-db-report.json`
and are not copied back into the database.

### 2. Copy

Provision RustFS on a **new** volume with the same bucket name. Then:

```bash
DST_S3_ENDPOINT=http://127.0.0.1:9002 \
DST_S3_ACCESS_KEY=... DST_S3_SECRET_KEY=... \
DST_S3_BUCKET=fairdatahive-catalog \
python scripts/migrate_objects.py copy --manifest var/migrate-manifest.jsonl
```

The script is resumable (`copied` in the manifest) and retries failed keys.
Preserving bucket + key means `distribution.download_url` does not need a rewrite.

For a small catalog, freeze writes for the entire copy. For a large catalog: initial
copy → write freeze → `copy` again (delta) → verify. Do not implement dual writes.

Encrypted source objects must be read through the source API and written through
the destination API. Copying raw ciphertext is not portable.

### 3. Verify

```bash
python scripts/migrate_objects.py verify --manifest var/migrate-manifest.jsonl
```

Every key and byte size must match. SHA-256 is streamed; a multipart ETag is
**not** a content hash. Sampled hashing is a reduced-assurance exception that
needs an explicit operational decision.

Re-run `db-check` after verify. Block cutover if any required feature (encryption,
versions, retention) cannot be represented on RustFS.

### 4. Cutover

1. Confirm freeze, verified manifest, database backup, pinned old/new configs.
2. Point the API at RustFS (`S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
   `S3_PUBLIC_ENDPOINT`). Keep a stable public hostname if you have one.
3. Restart the API. Check `/api/v1/health/ready`.
4. Smoke: public download, private 403, draft owner download, new upload, delete.
5. Fetch a **new** presigned URL and checksum the file. Old URLs may die when
   routing or credentials change.
6. Resume writes only after smoke checks pass. Watch 403/signature errors,
   upload failures, and deletion retries.
7. Isolate MinIO from writes for 14 days (or the agreed window).

### 5. Rollback

**Before any new RustFS write:** switch `S3_*` back to the retained MinIO
configuration and retest.

**After new writes:** freeze again, copy new/changed/deleted objects **and**
database references back to MinIO, verify, then switch. Do not blindly restore
the pre-cutover Postgres dump — that drops post-cutover catalog work.

If reverse reconciliation cannot meet the recovery objective, keep the service
read-only while repairing RustFS rather than declaring rollback complete.

Migration is finished only after a restore from the **new** RustFS backup chain
succeeds. Erasure coding is not an off-host backup.

## Acceptance checklist

- [ ] `S3_*` / `MINIO_*` precedence tested; secrets not logged
- [ ] Clean Compose install provisions a private bucket; recreate preserves objects
- [ ] Pinned RustFS + current SDK pass `make test-storage`
- [ ] Public-host signed GET, expiry, tamper, and anonymous access tested
- [ ] Existing private/draft access rules unchanged
- [ ] Encryption/versioning/retention either unused or explicitly handled
- [ ] Every uploaded `distribution.download_url` resolves on RustFS
- [ ] Counts, sizes, metadata, and agreed SHA-256 verification pass
- [ ] Post-cutover reverse-reconciliation path is written down
- [ ] Old MinIO remains isolated through the rollback window
- [ ] Restore from the RustFS backup chain meets the recovery objective
