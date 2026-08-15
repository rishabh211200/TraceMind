#!/usr/bin/env bash
set -e

echo "=== 1. Checking Python Code Formatting & Linting (Ruff) ==="
ruff check .
ruff format --check .

echo "=== 2. Checking Static Types (Mypy) ==="
mypy packages apps tests

echo "=== 3. Running Pytest Suite ==="
pytest tests/ -v

echo "=== 4. Checking Frontend TypeScript & Build ==="
cd frontend
npm run type-check
npm run build
cd ..

echo "=== All Checks Passed Successfully! ==="
