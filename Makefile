.PHONY: help dev dev-api dev-worker dev-beat dev-fe up down logs ps migrate migrate-new alembic upgrade downgrade lint format typecheck test test-engine clean install install-be install-fe install-browsers

help:
	@echo "Crawler dev targets:"
	@echo "  make dev          - chạy docker compose dev (postgres + redis) + API + worker ( громадно)"
	@echo "  make dev-fe       - chạy Vite dev server frontend (mặc định :5173)"
	@echo "  make up           - chỉ start postgres + redis"
	@echo "  make down         - stop docker compose dev"
	@echo "  make migrate      - áp dụng alembic upgrade head"
	@echo "  make migrate-new M=msg - tạo migration mới"
	@echo "  make test-engine  - chạy smoke crawl_one (cần POSTGRES+REDIS up)"
	@echo "  make lint / fmt / typecheck / test"

# ===== Docker dev infra =====
up:
	docker compose -f infra/docker-compose.dev.yml up -d postgres redis

down:
	docker compose -f infra/docker-compose.dev.yml down

logs:
	docker compose -f infra/docker-compose.dev.yml logs -f

ps:
	docker compose -f infra/docker-compose.dev.yml ps

# ===== Backend local dev =====
dev-api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 --app-dir backend

dev-worker:
	celery -A app.worker.celery_app worker --loglevel=INFO --concurrency=2 -Q crawl,schedule,webhook,export -P prefork

dev-beat:
	celery -A app.worker.celery_app beat --loglevel=INFO

dev-fe:
	cd frontend && pnpm dev

dev: up
	@echo "Infra started. Mở 2 terminal: 'make dev-api' và 'make dev-worker' (và 'make dev-beat')"

# ===== Alembic =====
migrate:
	cd backend && alembic upgrade head

migrate-new:
	@test -n "$(M)" || (echo "Usage: make migrate-new M='create jobs table'"; exit 1)
	cd backend && alembic revision --autogenerate -m "$(M)"

upgrade:
	cd backend && alembic upgrade head

downgrade:
	cd backend && alembic downgrade -1

# ===== Lint / tests =====
lint:
	ruff check backend/app backend/tests

fmt:
	ruff format backend/app backend/tests
	ruff check --fix backend/app backend/tests

typecheck:
	mypy backend/app

test:
	pytest backend/tests -v

test-engine:
	python -m backend.app.worker.tasks crawl_one --job-config scripts/smoke-job.yaml

# ===== Setup =====
install-be:
	python -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -e 'backend[dev]'

install-fe:
	cd frontend && pnpm install

install: install-be install-fe

install-browsers:
	playwright install chromium

# ===== Cleanup =====
clean:
	rm -rf backend/**/__pycache__ backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +