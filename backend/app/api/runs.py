"""Runs API: list, get, start, cancel + SSE event stream."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.db import session_scope
from app.deps import CurrentUser, DbSession, require_scope
from app.models import Job, User
from app.schemas.common import Page
from app.schemas.runs import JobRunRead, RunStartRequest
from app.services import job_service, run_service

router = APIRouter(tags=["runs"])


async def _check_job_ownership(db: AsyncSession, job_id: str, user: User) -> Job:
    try:
        return await job_service.get_job(
            db, job_id, owner_id=None if user.is_superuser else str(user.id)
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e


@router.get("/jobs/{job_id}/runs", response_model=Page[JobRunRead])
async def list_runs_for_job(
    job_id: str,
    db: DbSession,
    user: CurrentUser,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> Page[JobRunRead]:
    await _check_job_ownership(db, job_id, user)
    res = await run_service.list_runs(db, job_id=job_id, status=status_filter, page=page, size=size)
    return Page(
        items=[JobRunRead.model_validate(r) for r in res.items],
        page=res.page,
        size=res.size,
        total=res.total,
        pages=res.pages,
    )


@router.get("/runs", response_model=Page[JobRunRead])
async def list_all_runs(
    db: DbSession,
    user: CurrentUser,
    job_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> Page[JobRunRead]:
    if job_id:
        await _check_job_ownership(db, job_id, user)
    res = await run_service.list_runs(db, job_id=job_id, status=status_filter, page=page, size=size)
    return Page(
        items=[JobRunRead.model_validate(r) for r in res.items],
        page=res.page,
        size=res.size,
        total=res.total,
        pages=res.pages,
    )


@router.get("/runs/{run_id}", response_model=JobRunRead)
async def get_run(run_id: str, db: DbSession, user: CurrentUser) -> JobRunRead:
    try:
        run = await run_service.get_run_for_owner(
            db, run_id, owner_id=None if user.is_superuser else str(user.id)
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    return JobRunRead.model_validate(run)


@router.post("/jobs/{job_id}/runs", response_model=JobRunRead, status_code=status.HTTP_201_CREATED)
async def start_run(
    job_id: str,
    body: RunStartRequest,
    user: User = Depends(require_scope("jobs:run")),
) -> JobRunRead:
    async with session_scope() as db:
        job = await _check_job_ownership(db, job_id, user)
        try:
            run = await run_service.start_run(
                db, job=job, triggered_by=body.triggered_by, allow_concurrent=body.allow_concurrent
            )
        except run_service.JobNotRunnableError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
        except run_service.ConcurrentRunBlockedError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return JobRunRead.model_validate(run)


@router.post("/runs/{run_id}/cancel", response_model=JobRunRead)
async def cancel_run(
    run_id: str,
    user: User = Depends(require_scope("jobs:run")),
) -> JobRunRead:
    async with session_scope() as db:
        try:
            run = await run_service.get_run_for_owner(
                db, run_id, owner_id=None if user.is_superuser else str(user.id)
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
        except PermissionError as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
        try:
            run = await run_service.cancel_run(db, run)
        except run_service.RunError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return JobRunRead.model_validate(run)


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    db: DbSession,
    user: CurrentUser,
) -> EventSourceResponse:
    # Verify ownership trước để tránh leak events
    try:
        await run_service.get_run_for_owner(
            db, run_id, owner_id=None if user.is_superuser else str(user.id)
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e

    async def gen() -> AsyncIterator[dict[str, str]]:
        async for chunk in run_service.get_run_events(run_id):
            # chunk dạng "event: <e>\ndata: <json>\n\n"; convert sang dict cho sse-starlette
            event_name = "message"
            data = chunk
            try:
                parts = chunk.strip().split("\n")
                for line in parts:
                    if line.startswith("event: "):
                        event_name = line[len("event: ") :]
                    elif line.startswith("data: "):
                        data = line[len("data: ") :]
                yield {"event": event_name, "data": data}
            except Exception:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(gen())
