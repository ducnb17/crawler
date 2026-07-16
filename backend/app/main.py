"""Minimal FastAPI app: M1 (health/ready) + M2 (auth/users/jobs/runs/results)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import auth, jobs, results, runs, users
from app.config import get_settings
from app.core.db import dispose_engine, get_engine
from app.core.logging import configure_logging, logger
from app.core.redis import close_redis
from app.core.redis import health as redis_health


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("app_startup", env=get_settings().app_env)
    yield
    logger.info("app_shutdown")
    await dispose_engine()
    await close_redis()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Crawler API",
        version="0.2.0",
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs" if s.is_dev else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.api_cors.allow_origins,
        allow_credentials=s.api_cors.allow_credentials,
        allow_methods=s.api_cors.allow_methods,
        allow_headers=s.api_cors.allow_headers,
    )

    # Prometheus metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # Health/ready (M1)
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        from sqlalchemy import text

        db_ok = False
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                db_ok = True
        except Exception as e:
            logger.error("db_ready_failed", error=str(e))
        redis_ok = await redis_health()
        return {"db": db_ok, "redis": redis_ok}

    # Routers (M2)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(jobs.router)
    app.include_router(runs.router)
    app.include_router(results.router)

    return app


app = create_app()
