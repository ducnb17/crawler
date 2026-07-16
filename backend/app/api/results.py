"""Results API: list + filtered search + CSV/JSON export."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.results import ResultFilter, ResultRead
from app.services import result_service

router = APIRouter(prefix="/results", tags=["results"])


def _enforce_filter_for_user(f: ResultFilter, user: User) -> ResultFilter:
    """Non-superuser còn phải dùng filter theo job ownership; ở M2 ta chỉ
    giới hạn superuser được truy cập không theo job, còn userμό phải truyền job_id."""
    if not user.is_superuser and f.job_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "non-admin users must filter by job_id",
        )
    return f


@router.get("", response_model=Page[ResultRead])
async def list_results(
    db: DbSession,
    user: CurrentUser,
    q: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    url_contains: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    sort: str = "extracted_at:desc",
) -> Page[ResultRead]:
    f = _enforce_filter_for_user(
        ResultFilter(
            q=q,
            job_id=job_id,
            run_id=run_id,
            url_contains=url_contains,
            page=page,
            size=size,
            sort=sort,
        ),
        user,
    )
    return await result_service.list_results(
        db,
        job_id=f.job_id,
        run_id=f.run_id,
        q=f.q,
        url_contains=f.url_contains,
        page=f.page,
        size=f.size,
        sort=f.sort,
    )


@router.get("/export.csv")
async def export_csv(
    db: DbSession,
    user: CurrentUser,
    job_id: str | None = None,
    run_id: str | None = None,
    q: str | None = None,
    columns: str | None = Query(None, description="Comma-separated column names from data"),
) -> StreamingResponse:
    f = _enforce_filter_for_user(ResultFilter(job_id=job_id, run_id=run_id, q=q), user)
    cols: list[str] | None = columns.split(",") if columns else None
    csv_text = await result_service.stream_csv(
        db, job_id=f.job_id, run_id=f.run_id, q=f.q, columns=cols
    )

    async def gen() -> Any:
        yield csv_text

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


@router.get("/export.json")
async def export_json(
    db: DbSession,
    user: CurrentUser,
    job_id: str | None = None,
    run_id: str | None = None,
    q: str | None = None,
    columns: str | None = Query(None),
) -> StreamingResponse:
    f = _enforce_filter_for_user(ResultFilter(job_id=job_id, run_id=run_id, q=q), user)
    cols: list[str] | None = columns.split(",") if columns else None
    payload = await result_service.export_json(
        db, job_id=f.job_id, run_id=f.run_id, q=f.q, columns=cols
    )

    async def gen() -> Any:
        # Stream theo chunks để tránh tải full JSON trong 1 chunk
        yield payload

    return StreamingResponse(
        gen(),
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=results.json",
            "Content-Length": str(len(payload.encode("utf-8"))),
        },
    )
