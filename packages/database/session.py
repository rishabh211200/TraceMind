"""Database engine, connection pooling, and AsyncSession management."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.common.config import get_settings
from packages.common.logging import get_logger
from packages.database.models.base import Base

logger = get_logger("tracemind.database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine(database_url: str | None = None) -> AsyncEngine:
    """Create or return singleton AsyncEngine with optimized connection pooling."""
    global _engine
    if _engine is None or database_url is not None:
        url = database_url or get_settings().database_url
        engine_kwargs: dict[str, Any] = {
            "echo": False,
            "future": True,
        }
        # SQLite does not support pool_size / max_overflow
        if not url.startswith("sqlite"):
            engine_kwargs.update(
                {
                    "pool_size": 20,
                    "max_overflow": 10,
                    "pool_pre_ping": True,
                    "pool_timeout": 30,
                }
            )
        _engine = create_async_engine(url, **engine_kwargs)
    return _engine


def get_async_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create or return singleton async_sessionmaker."""
    global _session_factory
    if _session_factory is None or engine is not None:
        active_engine = engine or get_async_engine()
        _session_factory = async_sessionmaker(
            bind=active_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession with auto-rollback on exception."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Initialize all database tables from metadata."""
    active_engine = engine or get_async_engine()
    async with active_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_initialized")
