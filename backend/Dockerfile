# ===== Backend Dockerfile (API + Worker + Beat share this image) =====
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for Playwright + psycopg + build
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg2 ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libpangocairo-1.0-0 libgtk-3-0 \
    fonts-liberation xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata first for better layer caching
COPY pyproject.toml alembic.ini ./
COPY app/ ./app/

RUN pip install -e '.[dev]' 2>/dev/null || pip install -e '.' \
    && python -m playwright install chromium

EXPOSE 8001

# Default: run API. Override in compose for worker/beat.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8001", "-w", "2", "--timeout", "120"]