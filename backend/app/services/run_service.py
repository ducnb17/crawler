"""Run service: start/stop/status/list + SSE relay."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis
from app.core.logging import logger
from app.models import Job, JobRun
from app.schemas.common import Page
from app.worker.tasks import crawl_task


class RunError(Exception):
    pass


class JobNotRunnableError(RunError):
    pass


class ConcurrentRunBlockedError(RunError):
    pass


async def list_runs(
    db: AsyncSession,
    *,
    job_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[JobRun]:
    stmt = select(JobRun)
    if job_id:
        stmt = stmt.where(JobRun.job_id == job_id)
    if status:
        stmt = stmt.where(JobRun.status == status)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar_one())
    stmt = stmt.order_by(JobRun.created_at.desc()).offset((page - 1) * size).limit(size)
    items = list((await db.execute(stmt)).scalars().all())
    return Page(items=items, page=page, size=size, total=total, pages=(total + size - 1) // size)


async def get_run(db: AsyncSession, run_id: str) -> JobRun:
    run = (await db.execute(select(JobRun).where(JobRun.id == run_id))).scalar_one_or_none()
    if run is None:
        raise ValueError("run not found")
    return run


async def get_run_for_owner(db: AsyncSession, run_id: str, owner_id: str | None) -> JobRun:
    run = await get_run(db, run_id)
    if owner_id is not None:
        # must load job to check ownership
        job = (await db.execute(select(Job).where(Job.id == run.job_id))).scalar_one_or_none()
        if job is None or job.owner_id != owner_id:
            raise PermissionError("not owner")
    return run


async def start_run(
    db: AsyncSession,
    *,
    job: Job,
    triggered_by: str = "manual",
    allow_concurrent: bool = False,
) -> JobRun:
    if not job.start_urls:
        raise JobNotRunnableError("job has no start_urls")
    # Check concurrent runs
    if not allow_concurrent and not job.allow_concurrent_runs:
        active = (
            await db.execute(
                select(func.count())
                .select_from(JobRun.__table__)  # type: ignore[arg-type]
                .where(JobRun.job_id == job.id, JobRun.status.in_(["pending", "running"]))
            )
        ).scalar_one()
        if active and int(active) > 0:
            raise ConcurrentRunBlockedError("another run is in progress")
    run = JobRun(
        job_id=job.id,
        status="pending",
        triggered_by=triggered_by,
    )
    db.add(run)
    await db.flush()
    # enqueue Celery crawl_task
    crawl_task.apply_async(
        kwargs={"job_id": str(job.id), "run_id": str(run.id), "triggered_by": triggered_by},
        task_id=str(run.id),
    )
    logger.info("run_enqueued", job_id=str(job.id), run_id=str(run.id))
    return run


async def cancel_run(db: AsyncSession, run: JobRun) -> JobRun:
    if run.status not in ("pending", "running"):
        raise RunError(f"cannot cancel run in status '{run.status}'")
    run.status = "cancelled"
    run.ended_at = datetime.now(UTC)
    run.error = "cancelled by user"
    await db.flush()
    # Note: nếu đang chạy trong worker, ta *không* ép terminate (best-effort).
    # M2 để worker polling status trong job_runs (TODO: hook vào engine.stop)
    return run


async def get_run_events(run_id: str, last_id: str | None = None):  # type: ignore[no-untyped-def]
    """Async generator phát events từ Redis pubsub cho SSE.

    -LAST implement ở route handler dùng sse-starlette; đây là helper stream.
    """
    import asyncio
    import json

    r = redis.get_redis()
    channel = redis.ns(f"run:{run_id}")
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        # Gửi heartbeat để giữ connection
        yield "event: ping\ndata: {}\n\n"
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
            if msg is None:
                yield "event: ping\ndata: {}\n\n"
                continue
            payload = msg.get("data") if isinstance(msg, dict) else None
            if not payload:
                continue
            if isinstance(payload, (bytes, bytearray)):
                payload = payload.decode("utf-8", errors="replace")
            try:
                data = json.loads(payload)
                event_name = data.get("event", "progress")
                yield f"event: {event_name}\ndata: {payload}\n\n"
                if event_name in ("done", "error"):
                    return
            except Exception:
                yield f"event: raw\ndata: {payload}\n\n"
    except asyncio.CancelledError:
        return
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


__all__ = [
    "ConcurrentRunBlockedError",
    "JobNotRunnableError",
    "RunError",
    "cancel_run",
    "get_run",
    "get_run_events",
    "get_run_for_owner",
    "list_runs",
    "start_run",
]
