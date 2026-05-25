# Contributing to FairDataHive

Thank you for your interest in contributing. This project is a FAIR-compliant research data catalog (FastAPI, PostgreSQL/pgvector, MinIO, React).

## Repository

Clone and work in **one** directory (your fork or `~/Documents/fairdatahive`). Do not maintain a second copy under another path unless you sync deliberately.

## Getting started

1. Fork the repository on GitHub and clone your fork:
   ```bash
   git clone https://github.com/YOUR_USER/fairdatahive.git
   cd fairdatahive
   ```
2. Copy environment templates (never commit real `.env` files):
   ```bash
   cp .env.example .env
   cp frontend/.env.example frontend/.env
   ```
3. Install tooling once:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   cd frontend && npm ci && cd ..
   ```
4. Start the backend:
   ```bash
   make up
   # or API hot reload: make dev-api
   ```
5. Start the React UI (separate terminal):
   ```bash
   make dev-ui
   ```
   Open http://localhost:5173 (API on http://localhost:8002).

See [README.md](README.md) for troubleshooting.

## Branch and pull request workflow

```bash
git checkout main
git pull origin main
git checkout -b feature/short-description
# ... edit, test ...
make check
git add -p
git commit -m "Describe what and why"
git push -u origin feature/short-description
```

Open a pull request on GitHub. CI runs `pytest` and `npm run build`. Merge to `main` after checks pass.

## Running tests

```bash
source .venv/bin/activate
make test
# or: pytest tests/ -x -m "not integration"
```

Unit tests use an in-memory SQLite database. Tests marked `integration` require PostgreSQL with pgvector:

```bash
pytest tests/ -m "not integration"
```

## Code style

- **Python:** Follow existing patterns in `app/` — thin routers, logic in `services/`, Pydantic v2 schemas.
- **TypeScript/React:** Match conventions in `frontend/src/` (functional components, hooks).
- Keep changes focused; avoid unrelated refactors in the same pull request.

## Pull requests

1. Describe what changed and why.
2. Note how you tested (`make check`, manual URLs).
3. Do not include secrets, `.env` files, or `node_modules`.
4. If you change the React app and rely on `/ui/` in Docker, run `make build-ui` and commit `frontend/dist/` when appropriate.

## Questions

Open a GitHub issue for bugs, feature ideas, or documentation improvements.
