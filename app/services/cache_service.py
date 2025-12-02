from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.redis_url, decode_responses=True, encoding="utf-8"
        )
    return _client


async def reset_client() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # pragma: no cover
            pass
        _client = None


def make_cache_key(prefix: str, scope: str | None, payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]
    scope_part = scope or "_"
    return f"{prefix}:{scope_part}:{digest}"


async def get_json(key: str) -> Any | None:
    try:
        client = get_client()
        val = await client.get(key)
    except Exception as exc:  # pragma: no cover - cache failures are non-fatal
        logger.debug("cache get failed for %s: %s", key, exc)
        return None
    if val is None:
        return None
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return None


async def set_json(key: str, value: Any, ttl: int) -> None:
    try:
        client = get_client()
        await client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as exc:  # pragma: no cover
        logger.debug("cache set failed for %s: %s", key, exc)


async def invalidate_scope(scope: str | None) -> None:
    if scope is None:
        return
    try:
        client = get_client()
        patterns = [
            f"search:kw:{scope}:*",
            f"search:sem:{scope}:*",
            f"facets:{scope}",
        ]
        for pattern in patterns:
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor=cursor, match=pattern, count=200)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
    except Exception as exc:  # pragma: no cover
        logger.debug("cache invalidate failed for %s: %s", scope, exc)


async def ping() -> bool:
    try:
        client = get_client()
        return bool(await client.ping())
    except Exception:
        return False
