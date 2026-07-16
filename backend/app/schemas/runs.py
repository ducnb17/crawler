"""Job run schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class JobRunRead(ORMBase):
    id: str
    job_id: str
    status: str
    triggered_by: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    pages_crawled: int
    pages_failed: int
    items_extracted: int
    error: str | None = None
    return_code: int | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RunStartRequest(BaseModel):
    triggered_by: str = "manual"
    allow_concurrent: bool = False  # override job.allow_concurrent_runs
