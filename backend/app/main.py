"""Minimal FastAPI app skeleton (M2 sẽ hoàn thiện endpoints).

M1 chỉ expose `/health` + `/ready` + `/metrics` để có thể chạy server
để kiểm tra cấu hình + config + DB connection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.core.db import dispose_engine, get_engine
from app.core.logging import configure_logging, logger
from app.core.redis import close_redis
from app.core.redis import health as redis_health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
        version="0.1.0",
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs" if s.is_dev else None,
    )
    Instrumentator().instrument(app)
    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
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


app = create_app()
