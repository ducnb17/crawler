"""Results schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase, Page


class ResultRead(ORMBase):
    id: str
    job_id: str
    run_id: str | None = None
    url: str
    content_hash: str | None = None
    data: dict[str, Any]
    extracted_at: datetime


class ResultFilter(BaseModel):
    """Filter + search params for /results."""

    q: str | None = None  # full-text search (URL + data)
    job_id: str | None = None
    run_id: str | None = None
    url_contains: str | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=200)
    sort: str = "extracted_at:desc"  # field:direction


class ExportRequest(BaseModel):
    job_id: str | None = None
    run_id: str | None = None
    q: str | None = None
    columns: list[str] | None = None
    format: str = "csv"  # csv|json|excel (excel out-of-scope M2)


class ResultPage(Page[ResultRead]):
    pass
