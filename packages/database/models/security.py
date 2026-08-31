"""SQLAlchemy ORM models for Multi-Tenancy, Zero-Trust Authentication, and RBAC."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class TenantModel(Base):
    """SQLAlchemy model for organization tenants."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="ENTERPRISE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class UserModel(Base):
    """SQLAlchemy model for user accounts."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"usr_{uuid4().hex[:12]}"
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ApiKeyModel(Base):
    """SQLAlchemy model for programmatic API keys."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"key_{uuid4().hex[:12]}"
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key_name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    hashed_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class RevokedTokenModel(Base):
    """SQLAlchemy model for JWT blocklist / token revocation."""

    __tablename__ = "revoked_tokens"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"rev_{uuid4().hex[:12]}"
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(255), default="LOGOUT", nullable=False)


class TenantQuotaModel(Base):
    """SQLAlchemy model for tenant rate limits and resource quotas."""

    __tablename__ = "tenant_quotas"

    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    max_requests_per_minute: Mapped[int] = mapped_column(Integer, default=1200, nullable=False)
    max_concurrent_simulations: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_active_workflows: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
