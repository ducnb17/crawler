# Crawler — Async Web Crawler System

Production-grade async web crawler: quản lý nhiều **crawl jobs** qua REST +
realtime SSE, chạy trên pool worker (Celery + Redis), lưu kết quả vào
PostgreSQL. Hỗ trợ Playwright (サイト JS), Cloudflare bypass, proxy rotation,
webhook notification, schema auto-detect (AI), và dashboard Vue 3 đẹp mắt.

> **Đang trong giai đoạn rewrite theo milestone M1–M7.**
> Code Scrapy cũ đã sao lưu sang branch `legacy/old-scrapy`. M1 = scaffold +
> engine core. M2 = API + auth. M3 = frontend. M4 = advanced features.

## Stack

| Lớp | Công nghệ |
|---|---|
| Crawler engine | Python 3.12+, asyncio, httpx (HTTP/2), Playwright async fallback |
| Backend API | FastAPI + Pydantic v2 |
| Task queue | Celery + Redis (Redis cho frontier queue + dedup + locks + pubsub) |
| DB | PostgreSQL 16 (SQLAlchemy 2.0 async + Alembic), `pg_trgm` cho full-text |
| Auth | JWT RS256 + refresh token + RBAC scopes (M2) |
| Frontend | Vue 3 + Vite + TS + TailwindCSS + shadcn-vue + ECharts (M3) |
| Realtime | Server-Sent Events (SSE) cho crawl progress |
| Webhooks | Discord / Telegram / Slack / Email / HTTP generic + HMAC-SHA256 (M4) |
| Auto-detect | Heuristic + OpenAI gpt-4o-mini (off mặc định, M5) |
| Deploy | Docker multi-stage + docker-compose dev + Helm chart (M6) |

## Kiến trúc (M1)

```
backend/
├─ app/
│  ├─ main.py                  # FastAPI app (M1: /health /ready /metrics)
│  ├─ config.py                # pydantic-settings (env)
│  ├─ core/{db,redis,logging,security}.py
│  ├─ models/                  # SQLAlchemy ORM (jobs/users/results/proxies/webhooks)
│  ├─ schemas/                 # Pydantic request/response (M2+)
│  ├─ api/                     # REST endpoints (M2+)
│  ├─ services/                # business logic (M2+)
│  ├─ crawler/                 # ← THE NEW ENGINE
│  │  ├─ engine.py              #   orchestrator (frontier, semaphore, fetcher→extractor→DB flush)
│  │  ├─ fetcher.py             #   httpx + cloudscraper (CF) + Playwright fallback
│  │  ├─ browser_pool.py       #   shared Playwright browser/context pool
│  │  ├─ parser.py              #   HTML parse, CSS attr extract, regex, JSON-LD
│  │  ├─ extractor.py          #   per-job field extraction → dict rows
│  │  ├─ dedup.py               #   Redis SET url dedup
│  │  ├─ robots.py              #   robots.txt enforcement + cache
│  │  ├─ user_agents.py        #   SINGLE source of UA rotation + headers
│  │  ├─ antibot.py            #   Cloudflare detection
│  │  └─ middleware.py        #   pluggable request/response hooks
│  ├─ worker/
│  │  ├─ celery_app.py          #   Celery config + beat schedule
│  │  ├─ tasks.py               #   crawl_task, schedule_tick, send_webhook, export_task + CLI `crawl_one`
│  │  └─ beat.py
│  ├─ detect/                  # heuristic + LLM schema auto-detect (M5)
│  ├─ migrations/              # Alembic
│  └─ ...
├─ pyproject.toml
├─ alembic.ini
└─ tests/

infra/
├─ docker-compose.dev.yml      # postgres + redis
└─ postgres-init/01_extensions.sql

scripts/smoke-job.yaml          # config cho CLI smoke test (books.toscrape.com)

frontend/                       # Vue 3 SPA (M3)
```

## Quickstart (M1: dev)

### Yêu cầu
- Python 3.12+
- Docker (chạy postgres 16 + redis 7)
- Node 20+ / pnpm (chỉ khi tới M3)

### Cài đặt

```bash
# 1. Tạo venv + cài deps backend
make install-be            # hoặc: python -m venv .venv && pip install -e 'backend[dev]'

# 2. Cài Playwright browser
make install-browsers     # ~150MB Chromium

# 3. Sao chép env
cp .env.example .env

# 4. Khởi động postgres + redis
make up                   # docker compose -f infra/docker-compose.dev.yml up -d

# 5. Áp dụng alembic migration để tạo schema
make migrate
```

### Chạy

```bash
# Backend API (FastAPI dev)
make dev-api              # uvicorn --reload :8001

# Celery worker (cần nếu dùng crawl_task qua queue)
make dev-worker

# Celery beat (mấy scheduler, M4+cần)
make dev-beat

# Smoke-test engine (chạy 1 crawl trực tiếp, không cần DB):
make test-engine          # → chạy scripts/smoke-job.yaml
```

Mở `http://localhost:8001/docs` để xem OpenAPI.

### Tests / lint / type-check

```bash
make test                 # pytest
make lint                 # ruff check
make fmt                  # ruff format + fix
make typecheck            # mypy
```

Trạng thái build hiện tại: [ruff ✅, mypy ✅, pytest ✅ (19 tests)].

## Cấu hình 1 crawl job

Mỗi job = 1 row trong bảng `jobs` (sẽ CRUD qua UI ở M3). Field `fields` là JSON
map tên field → spec:

```jsonc
{
  "name": "books",
  "start_urls": ["https://books.toscrape.com/catalogue/page-1.html"],
  "allowed_domains": ["books.toscrape.com"],
  "item_container": "article.product_pod",
  "fields": {
    "title":       { "selector": "h3 a",   "attr": "title"  },
    "price":       { "selector": ".price_color", "transform": "price" },
    "availability":{ "selector": ".instock.availability", "transform": "strip" },
    "rating":      { "selector": ".star-rating", "attr": "class" },
    "url":         { "selector": "h3 a",   "attr": "href"   }
  },
  "next_page": "li.next a::attr(href)",
  "max_pages": 5,
  "max_depth": 1,
  "delay": 1.0,
  "render_js": false,
  "robots_obey": true,
  "concurrency": 2
}
```

Hỗ trợ selector: CSS (`h3 a`), CSS + attr (`h3 a::attr(href)`), regex post-process,
transform (`strip|lower|upper|int|float|price`), JSON-LD/schema.org fallback.

## Anti-bot & fetch order

1. `httpx.AsyncClient` (random UA + headers thật browser, retry/backoff cho
   408/429/500/502/503/504/520/522/524).
2. Cloudflare challenge (403/503 + `cf-mitigated` hoặc body markers) →
   `cloudscraper` fallback (sync lib chạy trong `asyncio.to_thread`).
3. Content thiếu (`< min_content_length`) hoặc job `render_js=True` →
   Playwright render (browser context pool chia sẻ, anti-detection stealth).

## Crawl execution flow

```
POST /jobs/{id}/run (M2)  ──▶ Celery crawl_task ──▶ CrawlerEngine.run()
   ↓                                                   │
DB: tạo job_runs row                          frontier queue (Redis List)
   ↓                                                   │
SSE /runs/{id}/events ◀── Redis pubsub ◀──── worker_pool (asyncio.Semaphore)
   ↓                                                   │
DB: results rows ghi batch (ON CONFLICT update)        │
                                                       ↓
                                              fetcher → extractor → _do_flush()
```

## Roadmap (M1–M7)

| Milestone | Nội dung | Status |
|---|---|---|
| M1 | Scaffold + core engine + workers + DB schema + CLI smoke | ✅ done |
| M2 | API đầy đủ: auth (JWT+RBAC), jobs CRUD, runs (start/stop), SSE, results list + export CSV/JSON | ⏳ next |
| M3 | Frontend Vue 3: login, jobs list + new job wizard (auto-detect), results table, SSE log viewer, dark mode | ⏳ |
| M4 | Proxy pool + health, webhook deliveries + test-send, schedule/beat, Excel export, FTS (pg_trgm) | ⏳ |
| M5 | AI schema auto-detect (heuristic + OpenAI), UI auto-detect button + preview | ⏳ |
| M6 | Prod hardening: Prometheus metrics, Sentry, structlog, Helm chart, HPA, CI/CD | ⏳ |
| M7 | Migration dữ liệu SQLite→Postgres, cleanup, finalize docs | ⏳ |

## Backup code cũ

Code Scrapy/Playwright cũ đã commit cuối nhánh branch `legacy/old-scrapy`:

```bash
git checkout legacy/old-scrapy   # xem/xem chạy thử bản trước rewrite
git checkout main                # quay lại bản mới
```

## Đóng góp

Xem `CLAUDE.md` cho convention (snake_case, comment tiếng Anh, user-facing tiếng
Việt, mọi HTTP phải try-catch + log).