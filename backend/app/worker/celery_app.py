"""Celery app config (Redis broker + backend, task routes)."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "crawler",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    # Serialization & privacy
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=24 * 3600,
    # Timeouts
    task_soft_time_limit=_settings.celery_task_soft_time_limit,
    task_time_limit=_settings.celery_task_time_limit,
    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    # Routes
    task_routes={
        "app.worker.tasks.crawl_task": {"queue": "crawl"},
        "app.worker.tasks.schedule_tick": {"queue": "schedule"},
        "app.worker.tasks.send_webhook": {"queue": "webhook"},
        "app.worker.tasks.export_task": {"queue": "export"},
    },
    task_default_queue="crawl",
    # Beat (scheduling)
    beat_schedule={
        # Quét jobs đã đến next_run_at mỗi 30s
        "schedule-tick": {
            "task": "app.worker.tasks.schedule_tick",
            "schedule": 30.0,
            "options": {"queue": "schedule"},
        },
        # Health check proxy mỗi 60s
        "proxy-health-tick": {
            "task": "app.worker.tasks.proxy_health_tick",
            "schedule": crontab(minute="*/1"),
            "options": {"queue": "schedule"},
        },
    },
    beat_scheduler="redbeat.RedBeatScheduler" if False else None,  # TODO chọn redbeat M4
    # Visibility timeout đủ lớn cho crawl task dài (vùng Redis)
    broker_transport_options={"visibility_timeout": 4000},
)
