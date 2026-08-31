"""Shared pytest fixtures and test utilities."""

import shutil
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from packages.common.config import Settings
from packages.database.models import Base
from packages.database.session import get_db_session


class AsyncTestSession:
    """Async session adapter wrapping SQLAlchemy synchronous Session for SQLite tests."""

    def __init__(self, sync_session: Session) -> None:
        self._sync = sync_session
        self.bind = sync_session.bind

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self._sync.execute(*args, **kwargs)

    async def commit(self) -> None:
        self._sync.commit()

    async def rollback(self) -> None:
        self._sync.rollback()

    async def refresh(self, obj: Any) -> None:
        self._sync.refresh(obj)

    async def merge(self, obj: Any) -> Any:
        return self._sync.merge(obj)

    async def flush(self) -> None:
        self._sync.flush()

    def add(self, obj: Any) -> None:
        self._sync.add(obj)

    def add_all(self, objs: list[Any]) -> None:
        self._sync.add_all(objs)

    async def delete(self, obj: Any) -> None:
        self._sync.delete(obj)

    async def close(self) -> None:
        self._sync.close()


@pytest.fixture
def test_settings() -> Settings:
    """Return test configuration settings."""
    return Settings(
        environment="test",
        debug=True,
        log_level="DEBUG",
    )


@pytest.fixture
def test_db_session():
    """In-memory SQLite test database session fixture."""
    from datetime import UTC, datetime

    from packages.database.models.security import TenantModel

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as sync_session:
        sys_tenant = TenantModel(
            id="tenant_system",
            name="TraceMind Default Organization",
            slug="tracemind-default",
            is_active=True,
            tier="enterprise",
            created_at=datetime.now(UTC),
        )
        sync_session.add(sys_tenant)
        sync_session.commit()
        yield AsyncTestSession(sync_session)
    Base.metadata.drop_all(engine)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Isolated test workspace directory fixture without OS tempfile symlink issues."""
    test_path = Path("data/test_workspace") / f"run_{int(time.time() * 1000)}"
    test_path.mkdir(parents=True, exist_ok=True)
    yield test_path
    shutil.rmtree(test_path, ignore_errors=True)


@pytest.fixture
async def async_client(test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client fixture with database dependency override and default admin credentials."""
    from packages.common.security.jwt import get_jwt_manager
    from packages.domain.security import Permission, Role

    async def override_get_db_session():
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    jwt_mgr = get_jwt_manager()
    admin_token = jwt_mgr.create_access_token(
        user_id="usr_admin",
        tenant_id="tenant_system",
        email="admin@tracemind.io",
        roles=[Role.PLATFORM_ADMIN],
        permissions=list(Permission),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as client:
        yield client
    app.dependency_overrides.clear()
