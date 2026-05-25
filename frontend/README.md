# FairDataHive UI

React + TypeScript catalog interface for the FairDataHive API.

## Features

- **Search** — keyword, semantic, or auto mode with facet filters
- **Catalog** — browse published resources (public or project scope)
- **Create** — metadata form, file upload, external/API distributions, optional publish
- **Resource detail** — versions, FAIR score, downloads, RDF/landing links
- **My resources** — owner drafts and published records
- **Access requests** — accept/reject incoming requests

## Quick start

1. Start the API (Docker or local uvicorn on port **8002**).
2. Enable dev auth in API `.env`: `DEV_AUTH_ENABLED=true`
3. Install and run the UI:

```bash
cd fairdatahive/frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` to the API.

**One dev server only** (port **5173**, `strictPort: true`). `npm run dev` stops any orphan on **5174**. To stop: `npm run dev:stop`.

## Auth

- With `VITE_DEV_AUTH=true`, the UI stores token `dev` (API accepts any request when `DEV_AUTH_ENABLED=true`).
- For Keycloak, paste a JWT into the token field in the header bar.

## Production build

```bash
npm run build
```

The API serves static files from `frontend/dist` at `/ui` when the folder exists.
