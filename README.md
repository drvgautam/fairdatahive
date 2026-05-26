# FairDataHive

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

FAIR-aligned research data catalog with a DCAT 3 metadata model, REST API, and web UI.  
**Stack:** FastAPI · PostgreSQL + pgvector · MinIO · Redis · React (Vite).

## Features

- Publish datasets with files, licenses, and FAIR scoring
- Public catalog search (keyword + semantic) and RDF / OAI-PMH export
- Private resources with access requests
- Docker Compose for local and production-style runs

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- For UI development: [Node.js](https://nodejs.org/) 20+
- For Python-only work: Python 3.12+

## Quick start

```bash
git clone https://github.com/drvgautam/fairdatahive.git
cd fairdatahive

cp .env.example .env
cp frontend/.env.example frontend/.env

docker compose build
docker compose up -d
```

| Service | URL |
|---------|-----|
| API docs | http://localhost:8002/docs |
| Swagger | http://localhost:8002/swagger |
| Built UI (from API image) | http://localhost:8002/ui |

`docker compose up -d` starts Postgres, MinIO, Redis, and the API only. Migrations run when the API container starts.

### Web UI (development)

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173** — Vite proxies `/api` to the API on port **8002**.

Set `VITE_DEV_AUTH=true` in `frontend/.env` to match `DEV_AUTH_ENABLED=true` in the API `.env` (default for local use).

## Common commands

Run from the repository root:

| Command | Purpose |
|---------|---------|
| `make up` | Start backend stack |
| `make down` | Stop stack |
| `make dev-api` | API with hot reload (bind-mounted `app/`) |
| `make dev-ui` | Vite dev server on :5173 |
| `make test` | Unit tests (SQLite) |
| `make check` | Tests + frontend build (before push) |
| `make build-api` | Build UI and refresh API image |

## Develop

**API hot reload (Docker):**

```bash
make dev-api
```

**Without Docker** (you provide Postgres 16 + pgvector, Redis, MinIO):

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # point DATABASE_URL at your Postgres
alembic upgrade head
uvicorn app.main:app --reload --port 8002
```

**Tests:**

```bash
make test
# Integration tests (need real Postgres + pgvector):
pytest tests/ -m integration
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch workflow, PRs, and CI.

## Deploy

For production: change all default passwords, set `DEV_AUTH_ENABLED=false`, configure Keycloak (`docker compose --profile auth up -d auth`), set `CORS_ORIGINS` and `MINIO_PUBLIC_ENDPOINT`, and restrict admin endpoints.

- Checklist: [SECURITY.md](SECURITY.md)
- Architecture, env vars, backups: project docs at `/docs` when the API is running (section **Deployment**), or [docs/index.html](docs/index.html#deployment)

## Configuration notes

Host ports differ from defaults to reduce clashes:

| Host port | Service |
|-----------|---------|
| 8002 | API |
| 5173 | Vite UI (dev) |
| 5434 | PostgreSQL |
| 9002 / 9003 | MinIO API / console |

If downloads open `http://minio:9000/...` in the browser, set `MINIO_PUBLIC_ENDPOINT=http://localhost:9002` in `.env` and recreate the `api` container.

More troubleshooting: [CONTRIBUTING.md](CONTRIBUTING.md) and API docs.

## Documentation

| Topic | Where |
|-------|--------|
| API reference | http://localhost:8002/swagger |
| UI guide, search, deployment | http://localhost:8002/docs |
| Frontend | [frontend/README.md](frontend/README.md) |
| Licenses & embeddings | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before opening a PR.

## License

[MIT](LICENSE)
