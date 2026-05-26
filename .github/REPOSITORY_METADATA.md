# GitHub repository metadata

Some settings appear **above the README** on the project home page (description, website, topics, social preview). They are configured on GitHub, not read automatically from most repo files.

## Apply with GitHub CLI

From a machine with `gh auth login` and maintainer access:

```bash
gh repo edit drvgautam/fairdatahive \
  --description "FAIR-compliant research data catalog (DCAT 3, FastAPI, PostgreSQL, React)" \
  --add-topic fair-data --add-topic dcat --add-topic research-data \
  --add-topic metadata --add-topic fastapi --add-topic postgresql \
  --add-topic python --add-topic react --add-topic open-science \
  --add-topic docker
```

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
