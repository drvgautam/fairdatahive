# GitHub repository metadata

Some settings appear **above the README** on the project home page (description, website, topics, social preview). They are configured on GitHub, not read automatically from most repo files.

## Public documentation site

**https://drvgautam.github.io/fairdatahive/**

Deployed from the [`docs/`](../docs/) folder via [`.github/workflows/pages.yml`](workflows/pages.yml) on each push to `main`.

Local copies while developing:

| URL | When |
|-----|------|
| http://localhost:8002/docs | API container running |
| http://localhost:5173/docs | Vite dev server |

## Apply with GitHub CLI

From a machine with `gh auth login` and maintainer access:

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

## Social preview image

1. Open **Settings → General → Social preview**.
2. Upload `assets/social-preview.svg` (export to PNG 1280×640 if GitHub requires raster), or screenshot the logo from the README.

## What is already in the repository

| Item | Location |
|------|----------|
| README logo & badges | `README.md`, `assets/logo.svg` |
| Issue templates | `.github/ISSUE_TEMPLATE/` |
| Pull request template | `.github/PULL_REQUEST_TEMPLATE.md` |
| Code of conduct | `CODE_OF_CONDUCT.md` |
| Security policy | `SECURITY.md` |
| Contributing | `CONTRIBUTING.md` |
