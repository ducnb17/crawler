"""Job schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import ORMBase


class JobBase(ORMBase):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_urls: list[str] = Field(default_factory=list, min_length=1)
    allowed_domains: list[str] = Field(default_factory=list)
    item_container: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    next_page: str | None = None
    follow_links: bool = False
    max_pages: int = Field(default=0, ge=0)
    max_depth: int = Field(default=0, ge=0)
    delay: float = Field(default=1.0, ge=0, le=300)
    render_js: bool = False
    robots_obey: bool = True
    concurrency: int = Field(default=0, ge=0, le=50)
    schedule_cron: str | None = None
    is_active: bool = False
    allow_concurrent_runs: bool = False
    proxy_profile_id: str | None = None
    webhook_id: str | None = None
    llm_detect_config: dict[str, Any] = Field(default_factory=dict)


class JobCreate(JobBase):
    @field_validator("start_urls")
    @classmethod
    def _urls_nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("at least one start_url is required")
        for u in v:
            if not u.startswith(("http://", "https://")):
                raise ValueError(f"url must start with http:// or https://: {u}")
        return v


class JobUpdate(ORMBase):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_urls: list[str] | None = None
    allowed_domains: list[str] | None = None
    item_container: str | None = None
    fields: dict[str, Any] | None = None
    next_page: str | None = None
    follow_links: bool | None = None
    max_pages: int | None = Field(default=None, ge=0)
    max_depth: int | None = Field(default=None, ge=0)
    delay: float | None = Field(default=None, ge=0, le=300)
    render_js: bool | None = None
    robots_obey: bool | None = None
    concurrency: int | None = Field(default=None, ge=0, le=50)
    schedule_cron: str | None = None
    is_active: bool | None = None
    allow_concurrent_runs: bool | None = None
    proxy_profile_id: str | None = None
    webhook_id: str | None = None
    llm_detect_config: dict[str, Any] | None = None


class JobRead(JobBase):
    id: str
    owner_id: str | None
    status: str
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
