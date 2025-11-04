from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError

from app.config import settings
from app.core.exceptions import UnauthorizedError


@dataclass
class CurrentUser:
    sub: str
    preferred_username: str | None = None
    email: str | None = None
    name: str | None = None
    roles: list[str] | None = None
    raw_claims: dict[str, Any] | None = None

    @property
    def display_name(self) -> str:
        return self.name or self.preferred_username or self.sub


_JWKS_CACHE: dict[str, Any] = {"keys": None, "expires_at": 0.0}
_JWKS_TTL = 3600.0

bearer_scheme = HTTPBearer(auto_error=False)


async def _fetch_jwks() -> dict[str, Any]:
    now = time.time()
    if _JWKS_CACHE["keys"] is not None and _JWKS_CACHE["expires_at"] > now:
        return _JWKS_CACHE["keys"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(settings.jwks_url)
        resp.raise_for_status()
        data = resp.json()
    _JWKS_CACHE["keys"] = data
    _JWKS_CACHE["expires_at"] = now + _JWKS_TTL
    return data


def _find_key(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    for k in jwks.get("keys", []):
        if kid is None or k.get("kid") == kid:
            return k
    return None


async def _decode_token(token: str) -> dict[str, Any]:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise UnauthorizedError("Invalid bearer token header.") from exc

    kid = unverified_header.get("kid")
    try:
        jwks = await _fetch_jwks()
    except Exception as exc:  # pragma: no cover - network errors mapped to 401
        raise UnauthorizedError(
            "Authentication keys unavailable; cannot verify token."
        ) from exc

    key = _find_key(jwks, kid)
    if key is None:
        raise UnauthorizedError("Signing key not found in JWKS.")

    algorithms = [key.get("alg", "RS256")]
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            options={"verify_aud": False},
            issuer=settings.issuer_url,
        )
    except JWTError as exc:
        raise UnauthorizedError(f"Token verification failed: {exc}") from exc

    return claims


def _user_from_claims(claims: dict[str, Any]) -> CurrentUser:
    sub = claims.get("sub")
    if not sub:
        raise UnauthorizedError("Token has no 'sub' claim.")
    roles = (
        claims.get("realm_access", {}).get("roles")
        if isinstance(claims.get("realm_access"), dict)
        else None
    )
    return CurrentUser(
        sub=sub,
        preferred_username=claims.get("preferred_username"),
        email=claims.get("email"),
        name=claims.get("name"),
        roles=roles,
        raw_claims=claims,
    )


def _dev_user() -> CurrentUser:
    return CurrentUser(
        sub=settings.dev_auth_sub,
        preferred_username="dev",
        email="dev@fairdatahive.local",
        name=settings.dev_auth_name,
        roles=["fairdatahive-admin"],
    )


async def _resolve_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> CurrentUser | None:
    override = getattr(request.app.state, "_auth_override", None)
    if callable(override):
        result = override(request, credentials)
        if hasattr(result, "__await__"):
            result = await result
        return result

    if settings.dev_auth_enabled:
        return _dev_user()

    if credentials is None or not credentials.credentials:
        return None
    claims = await _decode_token(credentials.credentials)
    return _user_from_claims(claims)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    user = await _resolve_user(request, credentials)
    if user is None:
        raise UnauthorizedError("Authentication required.")
    return user


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser | None:
    try:
        return await _resolve_user(request, credentials)
    except UnauthorizedError:
        return None
