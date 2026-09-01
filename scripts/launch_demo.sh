#!/usr/bin/env bash
set -e

echo "========================================================================"
echo "          🚀 LAUNCHING TRACEMIND DEMO TOPOLOGY & DATA SEEDER           "
echo "========================================================================"

# 1. Start demo containers in background
echo "[1/3] Building and starting isolated Docker containers..."
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build

# 2. Poll until API Gateway is healthy
echo "[2/3] Waiting for FastAPI Gateway and PostgreSQL to become healthy..."
READY=0
for i in {1..30}; do
  if docker compose -f docker-compose.demo.yml exec -T api curl -s -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "      ✓ API Gateway is healthy and accepting traffic."
    READY=1
    break
  fi
  echo "      ... waiting for services to initialize ($i/30) ..."
  sleep 2
done

if [ $READY -eq 0 ]; then
  echo "⚠️ Warning: API healthcheck timed out, attempting bootstrap anyway..."
fi

# 3. Seed deterministic demo data
echo "[3/3] Seeding 4 deterministic showcase scenarios..."
docker compose -f docker-compose.demo.yml exec -T api python scripts/demo_bootstrap.py

echo ""
echo "========================================================================"
echo "  ✅ TRACEMIND TECHNICAL SHOWCASE IS LIVE!"
echo "  👉 Open the 'Ports' tab in Codespaces and click Port 80 (or http://localhost)"
echo "  👉 Admin Login : admin@tracemind.io / TraceMind#Admin2026!"
echo "  👉 Viewer Login: viewer@tracemind.io / Viewer#Demo2026!"
echo "========================================================================"
