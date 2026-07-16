"""initial schema (users, jobs, proxies, webhooks, results)

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ===== users =====
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("full_name", sa.String(255)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("scopes", postgresql.JSON, nullable=False, server_default=sa.text("[]")),
        sa.Column("oauth_provider", sa.String(50)),
        sa.Column("oauth_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ===== refresh_tokens =====
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_agent", sa.Text),
        sa.Column("ip", sa.String(64)),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # ===== proxies =====
    op.create_table(
        "proxies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("owner_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("url", sa.String(255), nullable=False),
        sa.Column("scheme", sa.String(10), nullable=False, server_default=sa.text("'http'")),
        sa.Column("country", sa.String(2)),
        sa.Column("username", sa.String(255)),
        sa.Column("password", sa.String(255)),
        sa.Column("health_status", sa.String(20), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("health_details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("fail_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_proxies_url", "proxies", ["url"], unique=True)
    op.create_index("ix_proxies_owner_id", "proxies", ["owner_id"])

    # ===== proxy_profiles =====
    op.create_table(
        "proxy_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("owner_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("strategy", sa.String(30), nullable=False, server_default=sa.text("'round_robin'")),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("proxy_ids", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_proxy_profiles_name", "proxy_profiles", ["name"], unique=True)
    op.create_index("ix_proxy_profiles_owner_id", "proxy_profiles", ["owner_id"])

    # ===== webhooks =====
    op.create_table(
        "webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("owner_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret", sa.String(255)),
        sa.Column("events", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_webhooks_owner_id", "webhooks", ["owner_id"])

    # ===== jobs =====
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("owner_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("start_urls", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("allowed_domains", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("item_container", sa.String(500)),
        sa.Column("fields", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("next_page", sa.String(500)),
        sa.Column("follow_links", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("max_pages", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("max_depth", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("delay", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("render_js", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("robots_obey", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("concurrency", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("schedule_cron", sa.String(120)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("allow_concurrent_runs", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("proxy_profile_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("proxy_profiles.id", ondelete="SET NULL")),
        sa.Column("webhook_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("webhooks.id", ondelete="SET NULL")),
        sa.Column("llm_detect_config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_owner_status", "jobs", ["owner_id", "status"])
    op.create_index("ix_jobs_next_run_at", "jobs", ["next_run_at"])

    # ===== job_runs =====
    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("triggered_by", sa.String(30), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("pages_crawled", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("pages_failed", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("items_extracted", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text),
        sa.Column("return_code", sa.Integer),
        sa.Column("stats", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_runs_job_id", "job_runs", ["job_id"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])

    # ===== webhook_deliveries =====
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("webhook_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_run_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("job_runs.id", ondelete="SET NULL")),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("response_code", sa.Integer),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error", sa.Text),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])
    op.create_index("ix_webhook_deliveries_job_run_id", "webhook_deliveries", ["job_run_id"])

    # ===== results =====
    op.create_table(
        "results",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("job_runs.id", ondelete="SET NULL")),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("content_hash", sa.String(32)),
        sa.Column("data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_results_job_id", "results", ["job_id"])
    op.create_index("ix_results_run_id", "results", ["run_id"])
    op.create_index("ix_results_run_extracted", "results", ["run_id", "extracted_at"])
    op.create_unique_constraint("uq_results_job_url", "results", ["job_id", "url"])

    # full-text trên URL + data (pg_trgm gin index)
    op.execute("CREATE INDEX ix_results_url_trgm ON results USING gin (url gin_trgm_ops)")
    op.execute(
        "CREATE INDEX ix_results_data_trgm ON results "
        "USING gin ((data::text) gin_trgm_ops)"
    )

    # ===== audit_logs =====
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(50)),
        sa.Column("target_id", sa.String(36)),
        sa.Column("ip", sa.String(64)),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.execute("DROP INDEX IF EXISTS ix_results_data_trgm")
    op.execute("DROP INDEX IF EXISTS ix_results_url_trgm")
    op.drop_constraint("uq_results_job_url", "results")
    op.drop_index("ix_results_run_extracted", table_name="results")
    op.drop_index("ix_results_run_id", table_name="results")
    op.drop_index("ix_results_job_id", table_name="results")
    op.drop_table("results")

    op.drop_index("ix_webhook_deliveries_job_run_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_webhook_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_index("ix_job_runs_job_id", table_name="job_runs")
    op.drop_table("job_runs")

    op.drop_index("ix_jobs_next_run_at", table_name="jobs")
    op.drop_index("ix_jobs_owner_status", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_owner_id", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_webhooks_owner_id", table_name="webhooks")
    op.drop_table("webhooks")

    op.drop_table("proxy_profiles")
    op.drop_index("ix_proxy_profiles_owner_id", table_name="proxy_profiles")
    op.drop_index("ix_proxy_profiles_name", table_name="proxy_profiles")
    op.drop_table("proxy_profiles")

    op.drop_index("ix_proxies_url", table_name="proxies")
    op.drop_index("ix_proxies_owner_id", table_name="proxies")
    op.drop_table("proxies")

    op.drop_table("proxy_profiles")

    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")