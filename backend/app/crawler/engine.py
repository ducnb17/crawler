"""CrawlerEngine: orchestrator chính.

Input: JobConfig + run_id. Quản lý:
- Frontier queue trong Redis (breadth-first)
- Semaphore concurrency
- Fetcher (httpx/cloudscraper/playwright)
- Extractor
- Dedup
- Ghi results batch vào Postgres
- Progress events qua Redis pubsub
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.config import get_settings
from app.core import redis
from app.core.logging import logger
from app.crawler.dedup import is_seen, mark_seen
from app.crawler.extractor import extract_items, get_next_page, parse_field_specs
from app.crawler.fetcher import Fetcher
from app.crawler.robots import is_allowed
from app.models import Result


@dataclass(slots=True)
class JobConfig:
    """Config của 1 crawl job (load từ DB row `jobs`)."""

    job_id: str
    owner_id: str | None
    name: str
    start_urls: list[str]
    allowed_domains: list[str]
    item_container: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    next_page: str | None = None
    follow_links: bool = False
    max_pages: int = 0  # 0 = unlimited
    max_depth: int = 0  # 0 = depth limit for follow_links/next_page
    delay: float = 1.0
    render_js: bool = False
    robots_obey: bool = True
    concurrency: int = 0  # 0 = dùng default settings
    min_content_length: int = 0
    proxy: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_orm(cls, job: Any) -> JobConfig:
        s = get_settings()
        return cls(
            job_id=str(job.id),
            owner_id=str(job.owner_id) if job.owner_id else None,
            name=job.name,
            start_urls=list(job.start_urls or []),
            allowed_domains=list(job.allowed_domains or []),
            item_container=job.item_container,
            fields=dict(job.fields or {}),
            next_page=job.next_page,
            follow_links=bool(job.follow_links),
            max_pages=int(job.max_pages or 0),
            max_depth=int(job.max_depth or 0),
            delay=float(job.delay or s.crawler_min_delay),
            render_js=bool(job.render_js),
            robots_obey=bool(job.robots_obey),
            concurrency=int(job.concurrency or 0) or s.crawler_concurrency,
            min_content_length=s.crawler_min_content_length,
        )


@dataclass
class RunStats:
    pages_crawled: int = 0
    pages_failed: int = 0
    items_extracted: int = 0
    bytes_downloaded: int = 0
    retries: int = 0
    fallbacks_playwright: int = 0
    fallbacks_cloudscraper: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


PROGRESS_CHANNEL = "run:{run_id}"


class CrawlerEngine:
    def __init__(self, run_id: str, job: JobConfig):
        self.run_id = run_id
        self.job = job
        self.stats = RunStats()
        self._sem = asyncio.Semaphore(job.concurrency or get_settings().crawler_concurrency)
        self._stop_event = asyncio.Event()
        self._field_specs = parse_field_specs(job.fields)
        self._flush_q: list[dict[str, Any]] = []
        self._flush_lock = asyncio.Lock()
        self._flush_count_threshold = 50
        self._flush_interval = 5.0

    async def run(self) -> RunStats:
        """Main loop. Khởi tạo frontier, worker pool, flusher."""
        logger.info(
            "crawl_run_start", run_id=self.run_id, job_id=self.job.job_id, job_name=self.job.name
        )
        await self._publish("start", {"run_id": self.run_id, "job_id": self.job.job_id})
        # init frontier
        await redis.frontier_push(self.run_id, self.job.start_urls, depth=0)
        # flusher task
        flusher = asyncio.create_task(self._flush_loop())
        # worker pool
        workers = [
            asyncio.create_task(self._worker_loop(i)) for i in range(self.job.concurrency or 1)
        ]
        try:
            await asyncio.gather(*workers)
        finally:
            self._stop_event.set()
            flusher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await flusher
            await self._flush_all()
        logger.info(
            "crawl_run_done",
            run_id=self.run_id,
            pages=self.stats.pages_crawled,
            failed=self.stats.pages_failed,
            items=self.stats.items_extracted,
        )
        await self._publish(
            "done",
            {
                "pages_crawled": self.stats.pages_crawled,
                "pages_failed": self.stats.pages_failed,
                "items_extracted": self.stats.items_extracted,
                "fallbacks_playwright": self.stats.fallbacks_playwright,
                "fallbacks_cloudscraper": self.stats.fallbacks_cloudscraper,
            },
        )
        return self.stats

    async def stop(self) -> None:
        self._stop_event.set()

    # ===== Worker =====
    async def _worker_loop(self, idx: int) -> None:
        while not self._stop_event.is_set():
            item = await redis.frontier_pop(self.run_id)
            if item is None:
                if await self._all_done():
                    break
                await asyncio.sleep(0.3)
                continue
            url, depth = item
            await self._sem.acquire()
            try:
                await self._process_url(url, depth)
            finally:
                self._sem.release()
            # random delay giữa request
            if self.job.delay:
                await asyncio.sleep(
                    random.uniform(
                        max(0.1, self.job.delay * 0.7),
                        self.job.delay * 1.3,
                    )
                )

    async def _all_done(self) -> bool:
        return await redis.frontier_len(self.run_id) == 0

    async def _process_url(self, url: str, depth: int) -> None:
        # Stop conditions
        if self.job.max_pages and self.stats.pages_crawled >= self.job.max_pages:
            await self.stop()
            return
        # dedup
        if await is_seen(self.job.job_id, url):
            logger.debug("skip_seen", url=url)
            return
        # domain check
        if not self._allowed(url):
            logger.debug("skip_domain", url=url)
            return
        # robots
        if self.job.robots_obey and not await is_allowed(url):
            logger.info("skip_robots", url=url)
            return

        await mark_seen(self.job.job_id, url)
        fetcher = Fetcher(
            proxy=self.job.proxy,
            extra_headers=self.job.extra_headers,
        )
        try:
            result = await fetcher.fetch(
                url,
                force_render=self.job.render_js,
                min_content_length=self.job.min_content_length,
            )
        except Exception as e:
            logger.warning("fetch_exception", url=url, error=str(e))
            self.stats.pages_failed += 1
            await self._publish("page_failed", {"url": url, "error": str(e)})
            return

        if not result.ok:
            self.stats.pages_failed += 1
            await self._publish(
                "page_failed", {"url": url, "status": result.status, "error": result.error}
            )
            return

        self.stats.pages_crawled += 1
        self.stats.bytes_downloaded += len(result.text)
        if result.from_fallback == "playwright":
            self.stats.fallbacks_playwright += 1
        elif result.from_fallback == "cloudscraper":
            self.stats.fallbacks_cloudscraper += 1

        # extract items
        rows = extract_items(result.text, self.job.item_container, self._field_specs)
        for row in rows:
            row.setdefault("url", url)
            row["_source_url"] = url
            self.stats.items_extracted += 1
            await self._enqueue_for_flush(row)
        await self._publish(
            "page_done",
            {
                "url": url,
                "depth": depth,
                "status": result.status,
                "items": len(rows),
                "elapsed_ms": result.elapsed_ms,
                "fallback": result.from_fallback,
            },
        )

        # next page / follow links
        if self.job.next_page and (self.job.max_depth == 0 or depth < self.job.max_depth):
            next_url = get_next_page(result.text, self.job.next_page, url)
            if next_url and not await is_seen(self.job.job_id, next_url):
                await redis.frontier_push(self.run_id, [next_url], depth=depth + 1)

    # ===== DB flush =====
    async def _enqueue_for_flush(self, row: dict[str, Any]) -> None:
        async with self._flush_lock:
            self._flush_q.append(row)
            if len(self._flush_q) >= self._flush_count_threshold:
                await self._do_flush()
        if not self._stop_event.is_set() and self.stats.items_extracted % 100 == 0:
            await self._publish(
                "progress",
                {"pages_crawled": self.stats.pages_crawled, "items": self.stats.items_extracted},
            )

    async def _flush_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self._flush_interval)
            await self._do_flush()

    async def _flush_all(self) -> None:
        await self._do_flush()

    async def _do_flush(self) -> None:
        async with self._flush_lock:
            if not self._flush_q:
                return
            batch, self._flush_q = self._flush_q, []
        if not batch:
            return
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from app.core.db import get_session_maker

        sm = get_session_maker()
        async with sm() as s:
            try:
                rows_orm = [
                    {
                        "job_id": self.job.job_id,
                        "run_id": self.run_id,
                        "url": row.get("url") or row["_source_url"],
                        "content_hash": None,
                        "data": {k: v for k, v in row.items() if not k.startswith("_")},
                    }
                    for row in batch
                ]
                stmt = pg_insert(Result).values(rows_orm)
                # ON CONFLICT (job_id, url) DO UPDATE ghi đà data + run_id mới
                stmt = stmt.on_conflict_do_update(
                    index_elements=["job_id", "url"],
                    set_={
                        "run_id": stmt.excluded.run_id,
                        "data": stmt.excluded.data,
                        "extracted_at": datetime.now(UTC),
                    },
                )
                await s.execute(stmt)
                await s.commit()
            except Exception as e:
                await s.rollback()
                logger.error("flush_failed", error=str(e), batch_size=len(batch))

    # ===== Helpers =====
    def _allowed(self, url: str) -> bool:
        if not self.job.allowed_domains:
            return True
        host = (urlparse(url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in self.job.allowed_domains)

    async def _publish(self, event: str, payload: dict[str, Any]) -> None:
        try:
            await redis.publish(
                PROGRESS_CHANNEL.format(run_id=self.run_id),
                json.dumps({"event": event, "ts": datetime.now(UTC).isoformat(), **payload}),
            )
        except Exception as e:
            logger.debug("publish_failed", error=str(e))
