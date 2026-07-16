#!/usr/bin/env bash
# ===== Deploy script — run on VPS =====
# Usage: bash scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."
echo ">>> Working dir: $(pwd)"

# 1. Check Docker
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not installed. Install Docker first."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin not available."
  exit 1
fi

# 2. Prepare .env.prod
if [ ! -f .env.prod ]; then
  echo ">>> Creating .env.prod from .env.prod.example"
  cp .env.prod.example .env.prod
  echo "!!! EDIT .env.prod to set POSTGRES_PASSWORD and other secrets, then re-run."
  exit 0
fi

# 3. Generate JWT keys if missing
mkdir -p backend/secrets
if [ ! -f backend/secrets/jwt_rs256.pem ]; then
  echo ">>> Generating RSA keypair for JWT RS256"
  openssl genpkey -algorithm RSA -out backend/secrets/jwt_rs256.pem -pkeyopt rsa_keygen_bits:2048
  openssl rsa -in backend/secrets/jwt_rs256.pem -pubout -out backend/secrets/jwt_rs256.pub.pem
  chmod 600 backend/secrets/jwt_rs256.pem
fi

# 4. Build & start
echo ">>> Building and starting services..."
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build

# 5. Run migrations
echo ">>> Running Alembic migrations..."
docker compose -f infra/docker-compose.prod.yml exec -T backend alembic upgrade head || \
  echo "WARN: migration failed — run manually: docker compose -f infra/docker-compose.prod.yml exec backend alembic upgrade head"

echo ""
echo ">>> Done. Services:"
docker compose -f infra/docker-compose.prod.yml ps
echo ""
echo ">>> Frontend: http://$(hostname -I | awk '{print $1}')"
echo ">>> API docs (if dev mode): http://$(hostname -I | awk '{print $1}'):8001/docs"
echo ">>> Health: curl http://$(hostname -I | awk '{print $1}'):8001/health"