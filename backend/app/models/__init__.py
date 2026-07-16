"""SQLAlchemy ORM models — tập hợp toàn bộ schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid_pk() -> Mapped[str]:
    return mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


# ===== Users =====
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all,delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _now()
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


# ===== Proxies =====
class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[str] = _uuid_pk()
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    url: Mapped[str] = mapped_column(String(255), unique=True)
    scheme: Mapped[str] = mapped_column(String(10), default="http")
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    health_status: Mapped[str] = mapped_column(
        String(20), default="unknown"
    )  # healthy|degraded|blacklisted|unknown
    health_details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProxyProfile(Base):
    __tablename__ = "proxy_profiles"

    id: Mapped[str] = _uuid_pk()
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), unique=True)
    strategy: Mapped[str] = mapped_column(
        String(30), default="round_robin"
    )  # round_robin|weighted|geo|fallback
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    proxy_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ===== Webhooks =====
class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = _uuid_pk()
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    target_type: Mapped[str] = mapped_column(
        String(30)
    )  # discord|telegram|slack|generic_http|email|teams
    url: Mapped[str] = mapped_column(String(2048))
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    events: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    deliveries: Mapped[list[WebhookDelivery]] = relationship(cascade="all,delete-orphan")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = _uuid_pk()
    webhook_id: Mapped[str] = mapped_column(
        ForeignKey("webhooks.id", ondelete="CASCADE"), index=True
    )
    job_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_runs.id", ondelete="SET NULL"), index=True
    )
    event: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending|success|failed|retrying
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _now()


# ===== Jobs =====
class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = _uuid_pk()
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    start_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    allowed_domains: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    item_container: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    next_page: Mapped[str | None] = mapped_column(String(500), nullable=True)
    follow_links: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    max_pages: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_depth: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    delay: Mapped[float] = mapped_column(default=1.0, server_default="1.0")
    render_js: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    robots_obey: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    concurrency: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    schedule_cron: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    allow_concurrent_runs: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    proxy_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("proxy_profiles.id", ondelete="SET NULL")
    )
    webhook_id: Mapped[str | None] = mapped_column(ForeignKey("webhooks.id", ondelete="SET NULL"))
    llm_detect_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    status: Mapped[str] = mapped_column(
        String(20), default="draft", index=True
    )  # draft|active|paused|archived
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list[JobRun]] = relationship(back_populates="job", cascade="all,delete-orphan")

    __table_args__ = (Index("ix_jobs_owner_status", "owner_id", "status"),)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = _uuid_pk()
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )  # pending|running|done|failed|cancelled
    triggered_by: Mapped[str] = mapped_column(String(30), default="manual")  # manual|schedule|retry
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pages_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    items_extracted: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    return_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = _now()

    job: Mapped[Job] = relationship(back_populates="runs")


# ===== Results =====
class Result(Base):
    __tablename__ = "results"

    id: Mapped[str] = _uuid_pk()
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_runs.id", ondelete="SET NULL"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048))
    content_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("job_id", "url", name="uq_results_job_url"),
        Index("ix_results_run_extracted", "run_id", "extracted_at"),
        # pg_trgm full-text (sẽ tạo trong migration)
    )


# ===== Audit =====
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = _now()
