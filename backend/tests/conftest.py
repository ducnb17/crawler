"""Pytest config dùng chung cho toàn bộ test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://crawler:changeme@db.invalid:5432/crawler"
)
os.environ.setdefault("REDIS_URL", "redis://redis.invalid:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://redis.invalid:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://redis.invalid:6379/2")
os.environ.setdefault("ANTIBOT_USE_FAKE_USERAGENT", "false")
os.environ.setdefault("ANTIBOT_USE_CLOUDSCRAPER", "false")


@pytest.fixture(autouse=True)
def _reset_redis_singletons() -> Iterator[None]:
    """Mỗi test nên reset module-level singletons của redis/db."""
    from app.core import db, redis

    db._engine = None
    db._session_maker = None
    redis._redis = None
    yield
