"""Pydantic schemas for authentication, tenant lifecycle, user administration, and API keys."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from packages.domain.security import Permission, Role


class LoginRequest(BaseModel):
    """Payload for user password authentication."""

    email: str = Field(min_length=3, max_length=256, description="User email address")
    password: str = Field(min_length=1)
    tenant_id: str | None = Field(default=None, description="Optional tenant ID context")


class RegisterRequest(BaseModel):
    """Payload for user self-registration or initial setup."""

    email: str = Field(min_length=3, max_length=256, description="User email address")
    password: str = Field(min_length=8, description="Minimum 8 characters")
    full_name: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(default="tenant_system", description="Tenant to join")
    roles: list[Role] = Field(default_factory=lambda: [Role.VIEWER])


class RefreshTokenRequest(BaseModel):
    """Payload for single-use refresh token rotation."""

    refresh_token: str = Field(description="Active RS256 refresh token")


class TokenRevokeRequest(BaseModel):
    """Payload for revoking a token or session."""

    jti: str | None = None
    refresh_token: str | None = None
    reason: str = Field(default="LOGOUT")


class UserResponse(BaseModel):
    """Public user identity representation."""

    id: str
    tenant_id: str
    email: str
    full_name: str
    roles: list[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    """Payload for creating a user within a tenant by an admin."""

    email: str = Field(min_length=3, max_length=256, description="User email address")
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=128)
    roles: list[Role] = Field(default_factory=lambda: [Role.VIEWER])



class TenantCreate(BaseModel):
    """Payload for provisioning a new tenant organization."""

    name: str = Field(min_length=2, max_length=128)
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    tier: str = Field(default="ENTERPRISE")


class TenantResponse(BaseModel):
    """Public tenant organization representation."""

    id: str
    name: str
    slug: str
    is_active: bool
    tier: str
    created_at: datetime


class TenantQuotaResponse(BaseModel):
    """Resource limits and rate quotas for a tenant."""

    tenant_id: str
    max_requests_per_minute: int
    max_concurrent_simulations: int
    max_active_workflows: int
    max_retention_days: int


class TenantQuotaUpdate(BaseModel):
    """Payload for modifying tenant quota parameters."""

    max_requests_per_minute: int | None = Field(default=None, ge=10)
    max_concurrent_simulations: int | None = Field(default=None, ge=1)
    max_active_workflows: int | None = Field(default=None, ge=1)
    max_retention_days: int | None = Field(default=None, ge=1)


class ApiKeyCreate(BaseModel):
    """Payload for generating a scoped API key."""

    key_name: str = Field(min_length=1, max_length=128)
    scopes: list[Permission] = Field(default_factory=list)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    """Public API key representation (secret redacted)."""

    id: str
    tenant_id: str
    user_id: str | None
    key_name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response returned ONLY once upon creation containing the raw unhashed key."""

    full_key: str = Field(description="Full API key secret (copy immediately, never shown again)")


class CurrentUserResponse(BaseModel):
    """Profile payload for the currently authenticated session (/api/v1/auth/me)."""

    user_id: str
    tenant_id: str
    email: str
    roles: list[str]
    permissions: list[str]
    is_platform_admin: bool
    is_authenticated: bool
