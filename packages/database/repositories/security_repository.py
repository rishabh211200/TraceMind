"""Async repository for tenants, user authentication, API keys, and token revocations."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.security import (
    ApiKeyModel,
    RevokedTokenModel,
    TenantModel,
    TenantQuotaModel,
    UserModel,
)
from packages.domain.security import ApiKey, Role, Tenant, TenantQuotas, User


class SecurityRepository:
    """Async repository for tenant-scoped security domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ==========================================
    # Tenant Management
    # ==========================================
    async def create_tenant(self, tenant: Tenant) -> TenantModel:
        """Create a new multi-tenant organization."""
        model = TenantModel(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            tier=tenant.tier,
            created_at=tenant.created_at,
        )
        self.session.add(model)
        await self.session.flush()

        # Seed default tenant quotas
        quota_model = TenantQuotaModel(
            tenant_id=tenant.id,
            max_requests_per_minute=1200,
            max_concurrent_simulations=5,
            max_active_workflows=50,
            max_retention_days=90,
            created_at=datetime.now(UTC),
        )
        self.session.add(quota_model)
        await self.session.flush()
        return model

    async def get_tenant_by_id(self, tenant_id: str) -> TenantModel | None:
        """Retrieve tenant by unique identifier."""
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self.session.execute(stmt)
        tenant = result.scalar_one_or_none()
        if tenant is None and tenant_id == "tenant_system":
            tenant = TenantModel(
                id="tenant_system",
                name="TraceMind Default Organization",
                slug="tracemind-default",
                is_active=True,
                tier="enterprise",
                created_at=datetime.now(UTC),
            )
            self.session.add(tenant)
            await self.session.flush()
        return tenant

    async def get_tenant_by_slug(self, slug: str) -> TenantModel | None:
        """Retrieve tenant by URL-safe slug."""
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_tenants(self) -> list[TenantModel]:
        """List all registered tenants."""
        stmt = select(TenantModel).order_by(TenantModel.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ==========================================
    # User Management & Credentials
    # ==========================================
    async def create_user(self, user: User) -> UserModel:
        """Create a new user within a tenant."""
        model = UserModel(
            id=user.id or f"usr_{uuid4().hex[:12]}",
            tenant_id=user.tenant_id,
            email=user.email.lower().strip(),
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            roles=[r.value if isinstance(r, Role) else str(r) for r in user.roles],
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_user_by_id(self, user_id: str) -> UserModel | None:
        """Retrieve user by ID."""
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str, tenant_id: str | None = None) -> UserModel | None:
        """Retrieve user by email and optional tenant ID."""
        stmt = select(UserModel).where(UserModel.email == email.lower().strip())
        if tenant_id:
            stmt = stmt.where(UserModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users_for_tenant(self, tenant_id: str) -> list[UserModel]:
        """List all users belonging to a tenant."""
        stmt = (
            select(UserModel)
            .where(UserModel.tenant_id == tenant_id)
            .order_by(UserModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_last_login(self, user_id: str) -> None:
        """Update last login timestamp."""
        stmt = (
            update(UserModel).where(UserModel.id == user_id).values(last_login_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    # ==========================================
    # API Key Management
    # ==========================================
    async def create_api_key(self, api_key: ApiKey) -> ApiKeyModel:
        """Create a scoped API key."""
        model = ApiKeyModel(
            id=api_key.id or f"key_{uuid4().hex[:12]}",
            tenant_id=api_key.tenant_id,
            user_id=api_key.user_id,
            key_name=api_key.key_name,
            key_prefix=api_key.key_prefix,
            hashed_secret=api_key.hashed_secret,
            scopes=[s.value if hasattr(s, "value") else str(s) for s in api_key.scopes],
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_api_key_by_id(self, key_id: str) -> ApiKeyModel | None:
        """Retrieve API key by ID."""
        stmt = select(ApiKeyModel).where(ApiKeyModel.id == key_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_api_keys_by_prefix(self, prefix: str) -> list[ApiKeyModel]:
        """Retrieve active API keys matching prefix."""
        stmt = select(ApiKeyModel).where(
            ApiKeyModel.key_prefix == prefix,
            ApiKeyModel.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_api_keys_for_tenant(self, tenant_id: str) -> list[ApiKeyModel]:
        """List all API keys for a tenant."""
        stmt = (
            select(ApiKeyModel)
            .where(ApiKeyModel.tenant_id == tenant_id)
            .order_by(ApiKeyModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_api_key(self, key_id: str, tenant_id: str) -> bool:
        """Revoke / deactivate an API key."""
        stmt = (
            update(ApiKeyModel)
            .where(ApiKeyModel.id == key_id, ApiKeyModel.tenant_id == tenant_id)
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return bool(getattr(result, "rowcount", 0) > 0)

    # ==========================================
    # Token Revocation & Blocklist
    # ==========================================
    async def revoke_token(
        self,
        jti: str,
        tenant_id: str,
        user_id: str | None,
        expires_at: datetime,
        reason: str = "LOGOUT",
    ) -> RevokedTokenModel:
        """Add a JWT JTI to the revocation list."""
        model = RevokedTokenModel(
            id=f"rev_{uuid4().hex[:12]}",
            jti=jti,
            tenant_id=tenant_id,
            user_id=user_id,
            revoked_at=datetime.now(UTC),
            expires_at=expires_at,
            reason=reason,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def is_token_revoked(self, jti: str) -> bool:
        """Check whether a JTI is on the revocation blocklist."""
        stmt = select(RevokedTokenModel).where(RevokedTokenModel.jti == jti)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def cleanup_expired_revocations(self) -> int:
        """Remove expired revoked tokens to prevent unbounded table growth."""
        now = datetime.now(UTC)
        stmt = delete(RevokedTokenModel).where(RevokedTokenModel.expires_at < now)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(getattr(result, "rowcount", 0))

    # ==========================================
    # Tenant Quota Management
    # ==========================================
    async def get_tenant_quotas(self, tenant_id: str) -> TenantQuotaModel | None:
        """Retrieve quota configuration for tenant."""
        stmt = select(TenantQuotaModel).where(TenantQuotaModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_tenant_quotas(self, quotas: TenantQuotas) -> TenantQuotaModel:
        """Create or update quotas for tenant."""
        existing = await self.get_tenant_quotas(quotas.tenant_id)
        if existing:
            stmt = (
                update(TenantQuotaModel)
                .where(TenantQuotaModel.tenant_id == quotas.tenant_id)
                .values(
                    max_requests_per_minute=quotas.max_requests_per_minute,
                    max_concurrent_simulations=quotas.max_concurrent_simulations,
                    max_active_workflows=quotas.max_active_workflows,
                    max_retention_days=quotas.max_retention_days,
                )
            )
            await self.session.execute(stmt)
            await self.session.flush()
            updated = await self.get_tenant_quotas(quotas.tenant_id)
            return updated or existing
        else:
            model = TenantQuotaModel(
                tenant_id=quotas.tenant_id,
                max_requests_per_minute=quotas.max_requests_per_minute,
                max_concurrent_simulations=quotas.max_concurrent_simulations,
                max_active_workflows=quotas.max_active_workflows,
                max_retention_days=quotas.max_retention_days,
                created_at=quotas.created_at,
            )
            self.session.add(model)
            await self.session.flush()
            return model
