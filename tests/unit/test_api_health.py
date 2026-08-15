"""Unit tests for FastAPI health and root endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """Verify /api/v1/health returns HTTP 200 and all modules are ready."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "modules" in data
    assert data["modules"]["api"] == "operational"


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verify root / returns API metadata and docs link."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["docs"] == "/docs"
