#!/bin/sh
set -e

# Wait for PostgreSQL (hostname from DATABASE_URL, default: postgres)
DB_HOST="${DB_WAIT_HOST:-postgres}"
DB_PORT="${DB_WAIT_PORT:-5432}"
MAX_WAIT="${DB_WAIT_SECONDS:-60}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT} (up to ${MAX_WAIT}s)..."
elapsed=0
while ! python3 -c "
import socket
s = socket.socket()
s.settimeout(2)
s.connect(('${DB_HOST}', int('${DB_PORT}')))
s.close()
" 2>/dev/null; do
  elapsed=$((elapsed + 2))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "ERROR: PostgreSQL not reachable at ${DB_HOST}:${DB_PORT}" >&2
    exit 1
  fi
  sleep 2
done
echo "PostgreSQL is reachable."

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

# Explicit, idempotent bucket provisioning. The API never creates buckets at
# request time. Set PROVISION_STORAGE=false when the bucket is managed externally
# (e.g. AWS S3 with IAM that denies CreateBucket); the API still needs access.
if [ "${PROVISION_STORAGE:-true}" = "true" ]; then
  echo "Provisioning object storage bucket..."
  python3 -m app.tools.provision_storage --wait "${STORAGE_WAIT_SECONDS:-60}"
else
  echo "Checking object storage access..."
  python3 -m app.tools.provision_storage --check --wait "${STORAGE_WAIT_SECONDS:-60}"
fi

exec "$@"
