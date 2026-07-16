"""Jobs API: CRUD crawl jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import session_scope
from app.deps import CurrentUser, DbSession, require_scope
from app.models import User
from app.schemas.common import Page
from app.schemas.jobs import JobCreate, JobRead, JobUpdate
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=Page[JobRead])
async def list_jobs(
    db: DbSession,
    user: CurrentUser,
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> Page[JobRead]:
    owner_id = user.id if not user.is_superuser else None
    result = await job_service.list_jobs(
        db, owner_id=owner_id, status=status_filter, q=q, page=page, size=size
    )
    return Page(
        items=[JobRead.model_validate(j) for j in result.items],
        page=result.page,
        size=result.size,
        total=result.total,
        pages=result.pages,
    )


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreate,
    user: User = Depends(require_scope("jobs:write")),
) -> JobRead:
    async with session_scope() as db:
        job = await job_service.create_job(db, owner_id=str(user.id), data=body)
    return JobRead.model_validate(job)


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: str, db: DbSession, user: CurrentUser) -> JobRead:
    try:
        job = await job_service.get_job(
            db, job_id, owner_id=None if user.is_superuser else str(user.id)
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    return JobRead.model_validate(job)


@router.patch("/{job_id}", response_model=JobRead)
async def update_job(
    job_id: str,
    body: JobUpdate,
    user: User = Depends(require_scope("jobs:write")),
) -> JobRead:
    async with session_scope() as db:
        try:
            job = await job_service.get_job(
                db, job_id, owner_id=None if user.is_superuser else str(user.id)
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
        except PermissionError as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
        job = await job_service.update_job(db, job, body)
    return JobRead.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_job(
    job_id: str,
    user: User = Depends(require_scope("jobs:delete")),
) -> None:
    async with session_scope() as db:
        try:
            job = await job_service.get_job(
                db, job_id, owner_id=None if user.is_superuser else str(user.id)
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
        except PermissionError as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
        await job_service.delete_job(db, job)
