.PHONY: help install dev test lint format check build docker-up docker-down clean

help:
	@echo "TraceMind Developer Commands:"
	@echo "  make install     Install Python dependencies via uv and npm packages"
	@echo "  make dev         Run backend and frontend development servers"
	@echo "  make test        Run unit, integration, and contract tests"
	@echo "  make lint        Run Ruff linter and Mypy type checker"
	@echo "  make format      Autoformat Python code with Ruff"
	@echo "  make check       Run linting, type-checking, and tests"
	@echo "  make docker-up   Start local infrastructure via Docker Compose"
	@echo "  make docker-down Stop local infrastructure"
	@echo "  make clean       Clean build artifacts and cache"

install:
	uv pip install -e ".[dev,ml]"
	cd frontend && npm install

dev-backend:
	uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=packages --cov=apps --cov-report=term-missing

lint:
	ruff check .
	mypy packages apps tests

format:
	ruff format .
	ruff check --fix .

check: lint test

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage dist build frontend/dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
