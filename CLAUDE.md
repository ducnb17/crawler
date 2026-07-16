# CLAUDE.md

Hệ thống crawler async mới (Python 3.12+ / FastAPI / Celery / PostgreSQL /
Vue 3). Rewrite M1→M7. Code Scrapy cũ được backup trên branch `legacy/old-scrapy`.

## Build & Run Commands

Activate venv:
```bash
source .venv/bin/activate
```

Pull infra (Postgres + Redis):
```bash
make up                       # docker compose -f infra/docker-compose.dev.yml up -d
make down                     # stop
```

Migrate DB:
```bash
make migrate                  # alembic upgrade head
make migrate-new M="..."      # tạo migration mới
make downgrade                # lùi 1 revision
```

Run:
```bash
make dev-api                  # uvicorn --reload :8001
make dev-worker               # celery -A app.worker.celery_app worker ... (queues: crawl|schedule|webhook|export)
make dev-beat                 # celery beat
make test-engine              # smoke engine qua CLI (scripts/smoke-job.yaml)

make dev-fe                   # Vite frontend (chưa setup tới M3)
```

Lint / format / type-check / test:
```bash
make lint                     # ruff check
make fmt                      # ruff format + --fix
make typecheck                # mypy --config-file backend/pyproject.toml
make test                     # pytest backend/tests
```

## Code Style
- snake_case cho hàm/biến, PascalCase cho Class.
- Comment/docstring bằng tiếng Anh; user-facing (commit message, README, chat) có thể tiếng Việt.
- Mọi hàm HTTP Request đều phải try-catch và log lỗi rõ ràng (xem `app/crawler/fetcher.py`).
- Dùng `structlog` (`app.core.logging.logger`) không `print` (trừ CLI smoke).
- Type annotations bắt buộc — `mypy --strict` phải pass.
- Imports-in-function (`import cloudscraper`, `import time`) là cố ý để lazy-load heavy libs — ruff rule `PLC0415` đã bị ignore.

## Workflow & Safety
- Trả lời ngắn gọn, đi thẳng vào vấn đề.
- Luôn báo cho user biết file nào sắp sửa đổi trước khi ghi file.
- **Plan Mode** cho task lớn (multi-file, kiến trúc); Act Mode cho task nhỏ.
- Không commit trừ khi user yêu cầu; không push/PR khi chưa được nhờ.
- Branch `legacy/old-scrapy` chứa snapshot code Scrapy cũ, không sửa trên nhánh đó.

## Cấu trúc chính (M1)
- `backend/app/crawler/` — engine (fetcher, parser, extractor, dedup, robots, browser_pool, user_agents).
- `backend/app/worker/tasks.py` — Celery tasks + CLI `crawl_one`.
- `backend/app/models/__init__.py` — toàn bộ ORM (jobs/users/results/proxies/webhooks).
- `backend/app/migrations/versions/0001_initial_schema.py` — schema ban đầu + pg_trgm.
- `infra/docker-compose.dev.yml` — Postgres 16 + Redis 7 cho dev.
- `scripts/smoke-job.yaml` — config mẫu để smoke test engine.

## Key files for next milestones
- M2 routes: thêm vào `backend/app/api/` (auth, jobs, runs, results).
- M2 services: thêm vào `backend/app/services/`.
- LLM detect: `backend/app/detect/{heuristic,llm}.py`.
- Frontend: `frontend/` (Vite + Vue 3 + TS) — setup ở M3.