# FairDataHive

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A FAIR-compliant research data catalog implementing W3C DCAT 3 on top of PostgreSQL + pgvector + MinIO. Built with FastAPI 0.111, SQLAlchemy 2.0 async, Pydantic v2.

## License

This project is licensed under the [MIT License](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for embedding models and other dependencies.

## Development workflow

Use this repository at **`~/Documents/fairdatahive`** (or your clone) as the single working copy. Open that folder in your editor so tools and git match GitHub.

| Task | Command |
|------|---------|
| Start infra + API | `make up` or `docker compose up -d` |
| API with Python hot reload | `make dev-api` |
| React UI (HMR) | `make dev-ui` (separate terminal) |
| Run unit tests | `make test` |
| Pre-push check | `make check` |
| Stop stack | `make down` |

**GitHub:** work on feature branches, open PRs to `main`, wait for CI (`.github/workflows/ci.yml`) before merge. Never commit `.env`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for fork/PR details.

## Quick start

```bash
cd fairdatahive
cp .env.example .env   # required — sets DATABASE_URL host to "postgres" for Docker
cp frontend/.env.example frontend/.env

# Rebuild after compose/Dockerfile changes
docker compose build

# Start stack (migrations run automatically when the API container starts)
docker compose up -d postgres minio redis
docker compose up -d api
```

Or in one step (after `postgres` is healthy):

```bash
docker compose up -d
```

Docs: http://localhost:8002/docs · Swagger: http://localhost:8002/swagger (host **8002** → container 8000)

`docker compose up -d` starts **backend only** (Postgres, MinIO, Redis, API). It does **not** start the React dev server.

### Web UI (catalog)

**Development (recommended)** — local Vite on port **5173** only:

```bash
# Terminal 1 — backend (if not already running)
docker compose up -d

# Terminal 2 — frontend with hot reload
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open **http://localhost:5173** (proxies `/api` → http://localhost:8002).

Only **one** dev server runs (port **5173**). `npm run dev` stops any orphan on **5174** automatically. To stop manually: `npm run dev:stop`.

**Production-like UI** — static build served by the API:

```bash
make build-api
docker compose up -d --force-recreate api
```

Open **http://localhost:8002/ui/** (or http://localhost:8002/ which redirects there).

The Docker image includes `frontend/dist/` (run `make build-ui` before `docker compose build` when the UI changes). For daily UI work, prefer Vite on port **5173**.

**API hot reload** (Python only, no image rebuild per change):

```bash
make dev-api
```

Uses `docker-compose.dev.yml` — mounts `app/`, runs migrations once via a `migrate` service, then starts `uvicorn --reload` on port **8002**.

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Temporary failure in name resolution` for `postgres` | Ensure `.env` exists (`cp .env.example .env`) and `postgres` is running: `docker compose up -d postgres` then wait until healthy |
| Port `5432` already in use on host | Compose maps Postgres to **host port 5434** (`5434:5432`). Connect from the host with `localhost:5434` |
| Port `8000` or `8001` already in use on host | Compose maps the API to **host port 8002** (`8002:8000`). Open http://localhost:8002/docs or http://localhost:5173/docs |
| Port `6379` already in use on host | Redis is **not** published to the host; only the API container connects via `redis://redis:6379/0` on the internal network |
| Download opens `http://minio:9000/...` and fails in browser | Set `MINIO_PUBLIC_ENDPOINT=http://localhost:9002` in `.env` (keep `MINIO_ENDPOINT=http://minio:9000` for the API container), then recreate `api` |
| Port `9000` already in use on host | Compose maps MinIO to **host ports 9002** (API) and **9003** (console). Set `MINIO_PUBLIC_ENDPOINT=http://localhost:9002` |
| Nothing at http://localhost:5173 | Run `cd frontend && npm run dev` (with API on 8002), or use **http://localhost:8002/ui/** after `npm run build` |
| Same UI on **5173** and **5174** | A second Vite started when 5173 was busy. Run `cd frontend && npm run dev:stop` then `npm run dev` (only **5173** is used). Ignore **5174** — it should not be open |
| `Port 5173 is already in use` | Run `npm run dev:stop` in `frontend/`, or stop the other terminal's Vite |
| `EACCES` on `node_modules/.vite` | From `fairdatahive/`: `docker run --rm -v "$(pwd)/frontend:/app" -w /app node:20-alpine rm -rf /app/node_modules/.vite/deps` then `npm run dev` |
| `failed to set up container networking` on postgres | Stop the conflicting service on 5432, or change the host port in `docker-compose.yml` |
| Manual migrations only | `docker compose run --rm --entrypoint alembic api upgrade head` |

Optional Keycloak: `docker compose --profile auth up -d auth`

Open:

- Project docs: <http://localhost:8002/docs> (Vite dev: <http://localhost:5173/docs>)
- Swagger: <http://localhost:8002/swagger>
- React UI (dev): <http://localhost:5173> — `cd frontend && npm run dev` only
- React UI (built): <http://localhost:8002/ui>
- Catalog (Turtle): <http://localhost:8002/api/v1/catalog.ttl>
- OAI-PMH: <http://localhost:8002/api/v1/oai?verb=Identify>
- Metrics: <http://localhost:8002/metrics>

## Catalog search

The UI search page (`/search` on the Vite dev server) supports **keyword**, **semantic**, and **auto** modes:

| Mode | Use for |
|------|---------|
| **Keyword** | Titles, themes, and keyword tags (including short or comma-separated tags). PostgreSQL full-text search plus a token fallback when FTS misses stop words. |
| **Semantic** | Natural-language questions; cosine similarity over embeddings computed **at publish time** (sentence-transformers + pgvector). |
| **Auto** (default) | Keyword first; merges semantic hits when fewer than three keyword results. |

Only published, non-private resources in the selected scope are searchable. Configuration: `EMBEDDING_MODEL`, `SEMANTIC_SEARCH_THRESHOLD` (default `0.30`). Full detail: [project docs → Search engine](docs/index.html#search-detail) (also at `/docs` when the API is running).

## Local development (without Docker)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head            # against a local Postgres
uvicorn app.main:app --reload
```

## Running tests

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/ -x
```

Unit tests run against an in-memory SQLite database. Tests marked `@pytest.mark.integration` require a real PostgreSQL with pgvector — skip with `pytest -m "not integration"` if you don't have it.

## Repository layout

```
app/
  config.py           Pydantic Settings (all environment vars)
  database.py         Async SQLAlchemy engine + session factory
  main.py             FastAPI app factory + lifespan + router mount
  core/               Auth, exceptions, pagination, constants
  models/             SQLAlchemy ORM (single source of truth)
  schemas/            Pydantic v2 request/response contracts
  routers/            HTTP routing — thin layer
  services/           Business logic
alembic/              Database migrations
frontend/             React data-management UI (Vite + TypeScript)
static/               Served static assets (context.jsonld, dcat_ap_shapes.ttl)
templates/            Jinja2 templates (HTML landing page)
tests/                pytest-asyncio + httpx test client
```

## Deployment

Production deployment (Docker Compose, object storage, TLS, auth, backups) is documented in the project guide:

- <http://localhost:8002/docs#deployment> (or <http://localhost:5173/docs#deployment> during Vite dev)

## Security (production)

**Do not expose a public instance with default credentials.**

Before any internet-facing deployment:

1. Set `DEV_AUTH_ENABLED=false` and configure Keycloak (`docker compose --profile auth up -d auth`).
2. Replace Postgres, MinIO, and Redis passwords in `.env` (never commit `.env`).
3. Set `CORS_ORIGINS` to your real UI origin only.
4. Set `MINIO_PUBLIC_ENDPOINT` to the browser-reachable MinIO URL.
5. Restrict `/metrics`, MinIO console, and Keycloak admin to trusted networks.

See [SECURITY.md](SECURITY.md) for the full checklist and vulnerability reporting.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and pull request guidelines.

## Development phases

The app was built in five incremental phases (see commit history on `main`):

| Phase | Theme |
|------|------|
| 1 | Foundation: models, CRUD, upload, publish guard, presigned download |
| 2 | FAIR & RDF: FAIR score, license vocab, Turtle/JSON-LD, HTML landing |
| 3 | Search: PG full-text search, pgvector semantic search, Redis cache |
| 4 | Access: access requests, notifications, audit log, tombstones |
| 5 | Interop: OAI-PMH, DCAT-AP SHACL validation, DOI minting, metrics, indexes |
