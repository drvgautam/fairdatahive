# Security Policy

## Supported versions

Security fixes are applied to the latest release on the default branch. Older tags are not actively maintained unless noted in release notes.

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Report sensitive issues privately via **GitHub Security Advisories** (Security → Advisories → Report a vulnerability) on this repository, or email the maintainers listed in the repository profile. Include:

- Description of the issue and impact
- Steps to reproduce
- Affected version or commit
- Suggested fix (if any)

We aim to acknowledge reports within a few business days.

## Production deployment checklist

FairDataHive ships with **development defaults** that must be changed before any internet-facing deployment:

| Setting | Development | Production |
|---------|-------------|------------|
| `DEV_AUTH_ENABLED` | `false` in `.env.example` | **`false`** — use Keycloak JWT validation |
| `KEYCLOAK_CLIENT_ID` | Unset (aud not checked) | Set to your API OAuth client; JWT `aud` is verified |
| Postgres / RustFS / Redis passwords | Default compose values | Strong unique secrets |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `rustfsadmin` (local) | Restricted bucket-scoped key, not the RustFS root |
| `RUSTFS_ROOT_ACCESS_KEY` / `RUSTFS_ROOT_SECRET_KEY` | `rustfsadmin` | Root keys used only to bootstrap the store |
| `CORS_ORIGINS` | Local dev URLs | Explicit production UI origins only |
| Keycloak admin | Default in compose profile | Secured realm, no public admin console |
| `ENABLE_OPENAPI` / `ENABLE_METRICS` | `true` for local dev | Set **`false`** on public APIs unless behind VPN |
| `/metrics` | Exposed on API when `ENABLE_METRICS=true` | Disable or restrict to monitoring network |
| RustFS console (port 9003) | Loopback only | VPN or disabled publicly; never expose root keys to browsers |

Never commit `.env` files or real API keys to the repository.

## Dependency updates

Keep Python (`requirements.txt`) and Node (`frontend/package-lock.json`) dependencies updated. Review release notes for FastAPI, SQLAlchemy, and authentication-related packages.
