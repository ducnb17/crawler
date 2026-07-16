"""Result service: list/filter/search/export."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Result
from app.schemas.common import Page
from app.schemas.results import ResultRead


async def list_results(
    db: AsyncSession,
    *,
    job_id: str | None = None,
    run_id: str | None = None,
    q: str | None = None,
    url_contains: str | None = None,
    page: int = 1,
    size: int = 20,
    sort: str = "extracted_at:desc",
) -> Page[ResultRead]:
    stmt = select(Result)
    if job_id:
        stmt = stmt.where(Result.job_id == job_id)
    if run_id:
        stmt = stmt.where(Result.run_id == run_id)
    if url_contains:
        stmt = stmt.where(Result.url.ilike(f"%{url_contains}%"))
    if q:
        like = f"%{q}%"
        # ILIKE trên cả URL và data::text — pg_trgm gin index hỗ trợ
        stmt = stmt.where(or_(Result.url.ilike(like), Result.data.cast("text").ilike(like)))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar_one())
    # sort
    field, _, direction = sort.partition(":")
    col = getattr(Result, field, None) or Result.extracted_at
    stmt = stmt.order_by(col.asc()) if direction.lower() == "asc" else stmt.order_by(col.desc())
    stmt = stmt.offset((page - 1) * size).limit(size)
    rows = list((await db.execute(stmt)).scalars().all())
    items = [ResultRead.model_validate(r) for r in rows]
    return Page(items=items, page=page, size=size, total=total, pages=(total + size - 1) // size)


async def stream_csv(
    db: AsyncSession,
    *,
    job_id: str | None = None,
    run_id: str | None = None,
    q: str | None = None,
    columns: list[str] | None = None,
) -> str:
    """Stream CSV — gọi từ route response. Trả về full CSV string (M2 ok nếu <100K rows)."""
    stmt = select(Result)
    if job_id:
        stmt = stmt.where(Result.job_id == job_id)
    if run_id:
        stmt = stmt.where(Result.run_id == run_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Result.url.ilike(like), Result.data.cast("text").ilike(like)))
    rows = list((await db.execute(stmt.order_by(Result.extracted_at.desc()))).scalars().all())

    buf = io.StringIO()
    # detect columns tự động từ row đầu có data
    auto_cols: list[str] = []
    if not columns:
        for r in rows[:50]:
            auto_cols.extend(k for k in (r.data or {}) if k not in auto_cols)
        if not auto_cols:
            auto_cols = ["title", "price", "url"]
        columns_out: list[str] = ["id", "job_id", "run_id", "url", "extracted_at", *auto_cols]
        extra_cols = columns_out[5:]
    else:
        columns_out = columns
        extra_cols = columns  # caller-supplied full column order; ids not prefixed
    writer = csv.writer(buf)
    writer.writerow(columns_out)
    for r in rows:
        data = r.data or {}
        row: list[Any] = (
            [
                r.id,
                r.job_id,
                r.run_id or "",
                r.url,
                r.extracted_at.isoformat() if r.extracted_at else "",
            ]
            if not columns
            else []
        )
        for c in extra_cols:
            row.append(data.get(c, ""))
        writer.writerow(row)
    return buf.getvalue()


async def export_json(
    db: AsyncSession,
    *,
    job_id: str | None = None,
    run_id: str | None = None,
    q: str | None = None,
    columns: list[str] | None = None,
) -> str:
    stmt = select(Result)
    if job_id:
        stmt = stmt.where(Result.job_id == job_id)
    if run_id:
        stmt = stmt.where(Result.run_id == run_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Result.url.ilike(like), Result.data.cast("text").ilike(like)))
    rows = list((await db.execute(stmt.order_by(Result.extracted_at.desc()))).scalars().all())
    out: list[dict[str, Any]] = []
    for r in rows:
        item: dict[str, Any] = {
            "id": r.id,
            "job_id": r.job_id,
            "run_id": r.run_id,
            "url": r.url,
            "extracted_at": r.extracted_at.isoformat() if r.extracted_at else None,
        }
        data = r.data or {}
        if columns:
            item.update({c: data.get(c) for c in columns})
        else:
            item.update(data)
        out.append(item)
    return json.dumps(out, ensure_ascii=False, default=str)


__all__ = ["export_json", "list_results", "stream_csv"]
