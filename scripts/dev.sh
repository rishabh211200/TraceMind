#!/usr/bin/env bash
set -e

echo "Starting TraceMind local development stack..."

# Start background services
if command -v docker &> /dev/null; then
    docker compose up -d postgres redis
    echo "PostgreSQL & Redis containers running."
else
    echo "Docker not detected; using existing local database instances."
fi

# Run backend API in background
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

# Run frontend dev server
cd frontend && npm run dev &
FRONTEND_PID=$!

cleanup() {
    echo "Stopping TraceMind processes..."
    kill $API_PID || true
    kill $FRONTEND_PID || true
}

trap cleanup EXIT INT TERM
wait
