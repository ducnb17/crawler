"""Job service: CRUD operations + ownership enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models import Job
from app.schemas.common import Page
from app.schemas.jobs import JobCreate, JobUpdate


async def list_jobs(
    db: AsyncSession,
    *,
    owner_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = 20,
) -> Page[Job]:
    stmt = select(Job)
    if owner_id is not None:
        stmt = stmt.where(Job.owner_id == owner_id)
    if status:
        stmt = stmt.where(Job.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Job.name.ilike(like) | Job.description.ilike(like))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar_one())
    stmt = stmt.order_by(Job.created_at.desc()).offset((page - 1) * size).limit(size)
    items = list((await db.execute(stmt)).scalars().all())
    return Page(items=items, page=page, size=size, total=total, pages=(total + size - 1) // size)


async def get_job(db: AsyncSession, job_id: str, owner_id: str | None = None) -> Job:
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job is None:
        raise ValueError("job not found")
    if owner_id is not None and job.owner_id != owner_id:
        raise PermissionError("not owner")
    return job


async def create_job(db: AsyncSession, *, owner_id: str, data: JobCreate) -> Job:
    job = Job(
        owner_id=owner_id,
        name=data.name,
        description=data.description,
        start_urls=data.start_urls,
        allowed_domains=data.allowed_domains,
        item_container=data.item_container,
        fields=data.fields,
        next_page=data.next_page,
        follow_links=data.follow_links,
        max_pages=data.max_pages,
        max_depth=data.max_depth,
        delay=data.delay,
        render_js=data.render_js,
        robots_obey=data.robots_obey,
        concurrency=data.concurrency,
        schedule_cron=data.schedule_cron,
        is_active=data.is_active,
        allow_concurrent_runs=data.allow_concurrent_runs,
        proxy_profile_id=data.proxy_profile_id,
        webhook_id=data.webhook_id,
        llm_detect_config=data.llm_detect_config,
        status="active" if data.is_active else "draft",
    )
    if job.schedule_cron:
        job.next_run_at = _calc_next_run(job.schedule_cron)
    db.add(job)
    await db.flush()
    return job


async def update_job(db: AsyncSession, job: Job, data: JobUpdate) -> Job:
    changes: dict[str, Any] = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(job, k, v)
    if "is_active" in changes and "status" not in changes:
        job.status = "active" if job.is_active else "paused"
    if "schedule_cron" in changes or "is_active" in changes:
        job.next_run_at = (
            _calc_next_run(job.schedule_cron) if job.schedule_cron and job.is_active else None
        )
    await db.flush()
    return job


async def delete_job(db: AsyncSession, job: Job) -> None:
    await db.delete(job)
    await db.flush()


def _calc_next_run(cron_expr: str) -> datetime | None:
    try:
        from croniter import croniter

        return croniter(cron_expr, datetime.now(UTC)).get_next(datetime)
    except Exception as e:
        logger.warning("invalid_cron", expr=cron_expr, error=str(e))
        return None


__all__ = ["create_job", "delete_job", "get_job", "list_jobs", "update_job"]
