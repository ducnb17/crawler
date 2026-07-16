"""Application settings (env-driven) via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CorsSettings(BaseSettings):
    allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    allow_credentials: bool = True
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter=".",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== Application =====
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "crawler"
    app_log_level: str = "INFO"
    app_sentry_dsn: str = ""

    # ===== API =====
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    api_workers: int = 1
    api_public_base_url: str = "http://localhost:8001"
    api_cors: CorsSettings = Field(default_factory=CorsSettings)

    # ===== Database =====
    database_url: str = "postgresql+asyncpg://crawler:changeme@localhost:5432/crawler"
    pg_schema: str = "public"

    # ===== Redis / Celery =====
    redis_url: str = "redis://localhost:6379/0"
    redis_namespace: str = "crawler"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_worker_concurrency: int = 4
    celery_task_soft_time_limit: int = 3300
    celery_task_time_limit: int = 3600

    # ===== Auth =====
    auth_private_key_path: str = "./secrets/jwt_rs256.pem"
    auth_public_key_path: str = "./secrets/jwt_rs256.pub.pem"
    auth_access_token_ttl_min: int = 15
    auth_refresh_token_ttl_days: int = 7
    auth_password_schemes: str = "argon2"

    # ===== Crawler engine defaults =====
    crawler_user_agent: str = (
        "crawler-bot/1.0 (+https://github.com/your-org/crawler; contact: your-email@example.com)"
    )
    crawler_download_timeout: int = 30
    crawler_max_retries: int = 3
    crawler_backoff_cap: int = 60
    crawler_concurrency: int = 5
    crawler_min_delay: float = 1.0
    crawler_max_delay: float = 3.0
    crawler_min_content_length: int = 200
    crawler_browser_pool_size: int = 2
    crawler_proxy_timeout: int = 10
    crawler_proxy_fail_threshold: int = 3
    crawler_proxy_blacklist_ttl: int = 300

    # ===== Anti-bot =====
    antibot_cloudflare_max_retries: int = 2
    antibot_use_fake_useragent: bool = True
    antibot_use_cloudscraper: bool = True
    antibot_test_target_url: str = ""

    # ===== Webhooks =====
    webhook_delivery_max_attempts: int = 5
    webhook_delivery_timeout: int = 15

    # ===== LLM (auto-detect) =====
    llm_enabled: bool = False
    llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""

    # ===== S3/MinIO (Excel export lớn) =====
    s3_endpoint: str = ""
    s3_bucket: str = "crawler-exports"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    @field_validator("api_cors", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> object:
        # Accept comma-separated string from env
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return CorsSettings(allow_origins=parts)
        return v

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
