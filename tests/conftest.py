from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import AsyncIterator

# Force testing mode before anything else loads settings
os.environ["TESTING"] = "true"
os.environ["DEV_AUTH_ENABLED"] = "false"
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///:memory:"
)
os.environ.setdefault("BASE_URL", "http://localhost:8000")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minio")
os.environ.setdefault("MINIO_SECRET_KEY", "minio12345")
os.environ.setdefault("MINIO_BUCKET", "test-bucket")
os.environ.setdefault("KEYCLOAK_URL", "http://localhost:8080")
os.environ.setdefault("KEYCLOAK_REALM", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.database import Base


pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: tests that require a real PostgreSQL or external service",
    )


@pytest_asyncio.fixture
async def engine():
    import app.models  # noqa: F401 — register ORM tables on Base.metadata

    from app.config import get_settings

    get_settings.cache_clear()

    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def db(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
def test_user() -> CurrentUser:
    return CurrentUser(
        sub="user-test-1",
        preferred_username="tester",
        email="tester@example.org",
        name="Test User",
    )


@pytest_asyncio.fixture
async def client(session_factory, test_user) -> AsyncIterator[AsyncClient]:
    from app.main import app

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    def fake_auth(_request, _credentials):
        return test_user

    app.state._auth_override = fake_auth

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-token"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    app.state._auth_override = None
