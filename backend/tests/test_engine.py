"""Tests cho crawler.engine nguyên lý — cần mock redis + fetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.crawler.engine import CrawlerEngine, JobConfig


def _make_job() -> JobConfig:
    return JobConfig(
        job_id="job-1",
        owner_id=None,
        name="test",
        start_urls=["https://example.com/a"],
        allowed_domains=["example.com"],
        item_container="article",
        fields={"title": {"selector": "h2", "type": "text"}},
        max_pages=0,
        max_depth=0,
        delay=0,
        robots_obey=False,  # bỏ qua robots trong test
        concurrency=1,
    )


@pytest.mark.asyncio
async def test_engine_runs_with_mocked_dependencies() -> None:
    from app.core import redis

    # Mock redis get_redis + helpers
    rmock = AsyncMock()
    rmock.set = AsyncMock(return_value=True)
    rmock.delete = AsyncMock(return_value=1)
    rmock.sismember = AsyncMock(return_value=False)
    rmock.sadd = AsyncMock(return_value=1)
    rmock.rpush = AsyncMock(return_value=1)
    rmock.lpop = AsyncMock(side_effect=[None, None])
    # published
    rmock.publish = AsyncMock(return_value=1)

    with (
        patch.object(redis, "get_redis", return_value=rmock),
        patch.object(redis, "set_is_member", new=AsyncMock(return_value=False)),
        patch.object(redis, "set_add", new=AsyncMock(return_value=1)),
        patch.object(redis, "frontier_push", new=AsyncMock(return_value=1)),
        patch.object(
            redis,
            "frontier_pop",
            new=AsyncMock(side_effect=[("https://example.com/a", 0), None, None]),
        ),
        patch.object(redis, "frontier_len", new=AsyncMock(return_value=0)),
        patch.object(redis, "publish", new=AsyncMock(return_value=1)),
        patch("app.crawler.engine.mark_seen", new=AsyncMock(return_value=None)),
        patch("app.crawler.engine.is_seen", new=AsyncMock(return_value=False)),
    ):
        job = _make_job()
        engine = CrawlerEngine(run_id="run-1", job=job)
        # stub fetcher to return fake html
        from app.crawler.fetcher import FetchResult

        fake = FetchResult(
            url="https://example.com/a",
            status=200,
            text="<article><h2>Hi</h2></article>",
            headers={},
            elapsed_ms=5,
        )
        with (
            patch.object(Fetcher_placeholder_module, "Fetcher")
            if False
            else patch("app.crawler.engine.Fetcher") as fetcher_cls
        ):
            instance = AsyncMock()
            instance.fetch = AsyncMock(return_value=fake)
            fetcher_cls.return_value = instance
            # stub _do_flush để không truy cập DB
            engine._do_flush = AsyncMock()  # type: ignore[method-assignment]
            stats = await engine.run()
    assert stats.pages_crawled == 1
    assert stats.pages_failed == 0
    assert stats.items_extracted == 1


Fetcher_placeholder_module = type("M", (), {"Fetcher": None})
