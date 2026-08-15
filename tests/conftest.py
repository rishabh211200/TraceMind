"""Shared pytest fixtures and test utilities."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.common.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Return test configuration settings."""
    return Settings(
        environment="test",
        debug=True,
        log_level="DEBUG",
    )


@pytest.fixture
async def async_client():
    """Async HTTP client fixture for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
