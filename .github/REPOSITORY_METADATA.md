# GitHub repository metadata

## Public documentation site

**https://drvgautam.github.io/fairdatahive/**

Deployed from the [`docs/`](../docs/) folder via [`.github/workflows/pages.yml`](workflows/pages.yml) on each push to `main`.

Local copies while developing:

| URL | When |
|-----|------|
| http://localhost:8002/docs | API container running |
| http://localhost:5173/docs | Vite dev server |

## About section (description, topics, website)

Apply with GitHub CLI:

```bash
gh repo edit drvgautam/fairdatahive \
  --description "FAIR-compliant research data catalog (DCAT 3, FastAPI, PostgreSQL, React)" \
  --homepage "https://drvgautam.github.io/fairdatahive/" \
  --add-topic fair-data --add-topic dcat --add-topic research-data \
  --add-topic metadata --add-topic fastapi --add-topic postgresql \
  --add-topic python --add-topic react --add-topic open-science \
  --add-topic docker
```

## Enable GitHub Pages (first time)

1. **Settings → Pages → Build and deployment**
2. Source: **GitHub Actions** (not “Deploy from branch” — the workflow uploads `docs/`).
3. After the first successful **Deploy documentation** run, the site is live.

## Social preview

**Settings → General → Social preview** — upload `assets/social-preview.svg` from the repo root (export to PNG 1280×640 if required).
