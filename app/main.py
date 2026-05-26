from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers import (
    access,
    audit,
    catalog,
    files,
    health,
    interop,
    notifications,
    oai,
    rdf,
    resources,
    search,
    users,
)

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_PROJECT_DOCS = Path(__file__).resolve().parents[1] / "docs"

_background_tasks: set[asyncio.Task] = set()


async def _purge_loop() -> None:
    from app.services import access_service

    while True:
        try:
            await asyncio.sleep(6 * 60 * 60)
            await access_service.purge_expired()
        except asyncio.CancelledError:
            break
        except Exception as exc:  # pragma: no cover
            logger.warning("Background purge task: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.dev_auth_enabled:
        logger.warning(
            "DEV_AUTH_ENABLED is true: all API requests run as the dev user. "
            "Disable before any production deployment."
        )
    if not settings.testing:
        task = asyncio.create_task(_purge_loop())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    try:
        yield
    finally:
        for task in list(_background_tasks):
            task.cancel()
        for task in list(_background_tasks):
            try:
                await task
            except Exception:
                pass
        try:
            from app.database import dispose_engine
            await dispose_engine()
        except Exception:  # pragma: no cover
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="FairDataHive",
        version="1.0.0",
        description=(
            "FAIR-compliant research data catalog implementing DCAT 3 on top of "
            "PostgreSQL + pgvector + MinIO."
        ),
        lifespan=lifespan,
        docs_url="/swagger" if settings.enable_openapi else None,
        redoc_url="/redoc" if settings.enable_openapi else None,
    )

    register_exception_handlers(app)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    _ui_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if _ui_dist.is_dir():
        app.mount("/ui", StaticFiles(directory=str(_ui_dist), html=True), name="ui")

    if _PROJECT_DOCS.is_dir():
        app.mount(
            "/docs",
            StaticFiles(directory=str(_PROJECT_DOCS), html=True),
            name="project-docs",
        )

    api_prefix = "/api/v1"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(users.router, prefix=api_prefix)
    app.include_router(rdf.router, prefix=api_prefix)
    app.include_router(resources.router, prefix=api_prefix)
    app.include_router(catalog.router, prefix=api_prefix)
    app.include_router(files.router, prefix=api_prefix)
    app.include_router(search.router, prefix=api_prefix)
    app.include_router(access.router, prefix=api_prefix)
    app.include_router(notifications.router, prefix=api_prefix)
    app.include_router(audit.router, prefix=api_prefix)
    app.include_router(oai.router, prefix=api_prefix)
    app.include_router(interop.router, prefix=api_prefix)

    @app.get(
        f"{api_prefix}/context.jsonld",
        include_in_schema=True,
        response_model=None,
    )
    async def context_jsonld():
        path = _STATIC_DIR / "context.jsonld"
        if not path.exists():
            return JSONResponse({"error": "context.jsonld missing"}, status_code=404)
        return FileResponse(path, media_type="application/ld+json")

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "name": "FairDataHive",
            "version": "1.0.0",
            "docs": "/docs",
            "swagger": "/swagger",
            "openapi": "/openapi.json",
            "base_url": settings.base_url,
        }

    if settings.enable_metrics:
        try:
            from prometheus_fastapi_instrumentator import Instrumentator

            Instrumentator().instrument(app).expose(
                app, endpoint="/metrics", include_in_schema=False
            )
        except Exception as exc:  # pragma: no cover - metrics are optional
            logger.debug("Prometheus instrumentation unavailable: %s", exc)

    return app


app = create_app()
