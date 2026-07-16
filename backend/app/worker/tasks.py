"""Celery tasks: crawl_task (gọi engine), schedule_tick, send_webhook, export_task,
proxy_health_tick. Cộng CLI entry `crawl_one` để smoke test."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import yaml
from celery import Task, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.core.db import dispose_engine, session_scope
from app.core.logging import configure_logging, logger
from app.crawler.engine import CrawlerEngine, JobConfig
from app.models import Job, JobRun


# ===== Crawl task =====
@shared_task(
    bind=True,
    name="app.worker.tasks.crawl_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,
)
def crawl_task(
    self: Task, job_id: str, run_id: str | None = None, triggered_by: str = "manual"
) -> dict[str, Any]:
    """Load Job từ DB → JobConfig → CrawlerEngine.run()."""
    configure_logging()
    logger.info("crawl_task_received", job_id=job_id, run_id=run_id, triggered_by=triggered_by)
    try:
        return asyncio.run(_crawl_async(job_id, run_id, triggered_by))
    except SoftTimeLimitExceeded:
        logger.warning("crawl_soft_timeout", job_id=job_id, run_id=run_id)
        asyncio.run(_mark_run_failed(run_id, "soft_time_limit_exceeded"))  # type: ignore[arg-type]
        return {"job_id": job_id, "run_id": run_id, "status": "timeout"}
    except Exception as e:
        logger.exception("crawl_task_failed", job_id=job_id, run_id=run_id, error=str(e))
        asyncio.run(_mark_run_failed(run_id, str(e)))  # type: ignore[arg-type]
        raise


async def _crawl_async(job_id: str, run_id: str | None, triggered_by: str) -> dict[str, Any]:
    async with session_scope() as s:
        job = (await s.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        if not job:
            raise RuntimeError(f"job not found: {job_id}")
        job_cfg = JobConfig.from_orm(job)
        # tạo run row nếu chưa có
        run: JobRun | None = None
        if not run_id:
            run = JobRun(
                job_id=job.id,
                status="running",
                triggered_by=triggered_by,
                started_at=datetime.now(UTC),
            )
            s.add(run)
            await s.flush()
            run_id = str(run.id)
        else:
            run = (await s.execute(select(JobRun).where(JobRun.id == run_id))).scalar_one_or_none()
            if run:
                run.status = "running"
                run.started_at = datetime.now(UTC)
        await s.commit()
        # keep references (job was expunged after commit; reload minimal)
        job_id = str(job.id)
        run_id = str(run.id) if run else run_id

    # prepare queues/reset dedup for fresh run
    from app.core import redis

    r = redis.get_redis()
    await r.delete(redis.ns(f"frontier:{run_id}"))
    await redis.dedup_reset_dedup_set(
        job_id
    ) if False else None  # kept optional; we won't reset dedup here

    engine = CrawlerEngine(run_id=run_id, job=job_cfg)
    stats = await engine.run()

    async with session_scope() as s:
        run_db = (await s.execute(select(JobRun).where(JobRun.id == run_id))).scalar_one_or_none()
        if run_db:
            run_db.status = "done"
            run_db.ended_at = datetime.now(UTC)
            run_db.pages_crawled = stats.pages_crawled
            run_db.pages_failed = stats.pages_failed
            run_db.items_extracted = stats.items_extracted
            run_db.stats = {
                "bytes_downloaded": stats.bytes_downloaded,
                "fallbacks_playwright": stats.fallbacks_playwright,
                "fallbacks_cloudscraper": stats.fallbacks_cloudscraper,
                "duration_s": (datetime.now(UTC) - stats.started_at).total_seconds(),
            }
    await dispose_engine()
    return {
        "job_id": job_id,
        "run_id": run_id,
        "status": "done",
        "pages_crawled": stats.pages_crawled,
        "pages_failed": stats.pages_failed,
        "items_extracted": stats.items_extracted,
    }


async def _mark_run_failed(run_id: str | None, error: str) -> None:
    if not run_id:
        return
    async with session_scope() as s:
        run = (await s.execute(select(JobRun).where(JobRun.id == run_id))).scalar_one_or_none()
        if run:
            run.status = "failed"
            run.ended_at = datetime.now(UTC)
            run.error = error
    await dispose_engine()


# ===== Schedule tick =====
@shared_task(name="app.worker.tasks.schedule_tick")
def schedule_tick() -> dict[str, Any]:
    """Quét jobs do đến giờ, submit crawl_task."""
    configure_logging()
    return asyncio.run(_schedule_tick_async())


async def _schedule_tick_async() -> dict[str, Any]:
    from datetime import timedelta

    now = datetime.now(UTC)
    submitted: list[str] = []
    async with session_scope() as s:
        # chọn jobs active có next_run_at <= now
        stmt = select(Job).where(
            Job.is_active.is_(True),
            Job.next_run_at.is_not(None),
            Job.next_run_at <= now,
        )
        jobs = (await s.execute(stmt)).scalars().all()
        for job in jobs:
            triggered_id = str(uuid.uuid4())
            crawl_task.apply_async(
                kwargs={"job_id": str(job.id), "run_id": None, "triggered_by": "schedule"},
                task_id=triggered_id,
            )
            submitted.append(str(job.id))
            # advance next_run_at
            if job.schedule_cron:
                try:
                    from croniter import croniter

                    next_dt = croniter(job.schedule_cron, now).get_next(datetime)
                    job.next_run_at = next_dt
                except Exception as e:
                    logger.warning("cron_advance_failed", job_id=str(job.id), error=str(e))
                    job.next_run_at = now + timedelta(hours=1)
    return {"submitted": submitted, "count": len(submitted)}


# ===== Webhook delivery =====
@shared_task(
    bind=True,
    name="app.worker.tasks.send_webhook",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_webhook(
    self: Task, webhook_id: str, event: str, payload: dict[str, Any], job_run_id: str | None = None
) -> dict[str, Any]:
    """M2+ sẽ hoàn thiện HMAC-SHA256 + delivery logging; M1 stub."""
    logger.info("webhook_send_stub", webhook_id=webhook_id, event_name=event)
    return {"webhook_id": webhook_id, "event": event, "status": "stubbed"}


# ===== Export =====
@shared_task(name="app.worker.tasks.export_task")
def export_task(job_id: str, run_id: str | None, fmt: str = "csv") -> dict[str, Any]:
    """M2+ triển khai thực; M1 stub."""
    logger.info("export_stub", job_id=job_id, fmt=fmt)
    return {"status": "stubbed"}


# ===== Proxy health =====
@shared_task(name="app.worker.tasks.proxy_health_tick")
def proxy_health_tick() -> dict[str, Any]:
    """M4 triển khai pool health check; M1 stub."""
    return {"status": "stubbed"}


# ===== CLI smoke test =====
@click.group()
def cli() -> None:
    """Crawler CLI."""


@cli.command("crawl_one")
@click.option(
    "--job-config", "job_config_path", required=True, help="YAML config dùng cho smoke crawl"
)
@click.option("--run-id", default=None, help="ID run cụ thể (mặc định sinh mới)")
def crawl_one(job_config_path: str, run_id: str | None) -> None:
    """Chạy DIRECT (bypass Celery/DB) 1 crawl job từ YAML để smoke test engine.

    Không cần Postgres loaded (no DB writes); chỉ đảo HTML + log results ra console.
    """
    configure_logging()
    cfg_path = Path(job_config_path)
    with cfg_path.open() as fh:
        raw = yaml.safe_load(fh)
    job_id = raw.get("job_id") or f"smoke-{uuid.uuid4().hex[:8]}"
    run_id = run_id or f"smoke-run-{uuid.uuid4().hex[:8]}"
    job = JobConfig(
        job_id=job_id,
        owner_id=None,
        name=raw.get("name", "smoke"),
        start_urls=raw.get("start_urls", []),
        allowed_domains=raw.get("allowed_domains", []),
        item_container=raw.get("item_container"),
        fields=raw.get("fields", {}),
        next_page=raw.get("next_page"),
        follow_links=bool(raw.get("follow_links", False)),
        max_pages=int(raw.get("max_pages", 0)),
        max_depth=int(raw.get("max_depth", 0)),
        delay=float(raw.get("delay", 1.0)),
        render_js=bool(raw.get("render_js", False)),
        robots_obey=bool(raw.get("robots_obey", True)),
        concurrency=int(raw.get("concurrency", 0)),
        min_content_length=int(raw.get("min_content_length", 0)),
        extra_headers=dict(raw.get("extra_headers", {}) or {}),
    )
    # Override _do_flush để in ra stdout thay vì ghi DB
    engine = CrawlerEngine(run_id=run_id, job=job)
    engine._do_flush = _smoke_flush  # type: ignore[assignment]
    try:
        stats = asyncio.run(engine.run())
    except KeyboardInterrupt:
        logger.info("smoke_interrupted")
        return
    click.echo(
        json.dumps(
            {
                "job_id": job_id,
                "run_id": run_id,
                "pages_crawled": stats.pages_crawled,
                "pages_failed": stats.pages_failed,
                "items_extracted": stats.items_extracted,
                "fallbacks_playwright": stats.fallbacks_playwright,
                "fallbacks_cloudscraper": stats.fallbacks_cloudscraper,
            },
            indent=2,
        )
    )


async def _smoke_flush(self: CrawlerEngine) -> None:
    async with self._flush_lock:
        if not self._flush_q:
            return
        batch, self._flush_q = self._flush_q, []
    for row in batch:
        click.echo(
            json.dumps(
                {k: v for k, v in row.items() if not k.startswith("_")},
                default=str,
                ensure_ascii=False,
            )
        )


# celery CLI bind
main = cli

if __name__ == "__main__":
    cli()
