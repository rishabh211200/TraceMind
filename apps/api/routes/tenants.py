"""FastAPI routes for tenant organization lifecycle, quota enforcement, and user administration."""

from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
    require_permission,
)
from apps.api.exceptions import (
    ConflictException,
    EntityNotFoundException,
    ForbiddenException,
)
from apps.api.schemas.security import (
    TenantCreate,
    TenantQuotaResponse,
    TenantQuotaUpdate,
    TenantResponse,
    UserCreate,
    UserResponse,
)
from packages.common.security.crypto import PasswordHasher
from packages.database.repositories.security_repository import SecurityRepository
from packages.database.session import get_db_session
from packages.domain.security import (
    Permission,
    Tenant,
    TenantContext,
    TenantQuotas,
    User,
)

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenant Organizations & Governance"])
hasher = PasswordHasher()


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision New Tenant Organization",
    dependencies=[Depends(require_permission(Permission.TENANTS_MANAGE))],
)
async def create_tenant(
    req: TenantCreate,
    session: AsyncSession = Depends(get_db_session),
) -> TenantResponse:
    """Provision a new tenant organization with isolated storage and default quotas."""
    repo = SecurityRepository(session)
    existing = await repo.get_tenant_by_slug(req.slug)
    if existing:
        raise ConflictException(f"Tenant with slug '{req.slug}' already exists")

    tenant_id = f"tenant_{req.slug.replace('-', '_')}"
    tenant_domain = Tenant(
        id=tenant_id,
        name=req.name,
        slug=req.slug,
        is_active=True,
        tier=req.tier,
    )

    created = await repo.create_tenant(tenant_domain)
    await session.commit()

    return TenantResponse(
        id=created.id,
        name=created.name,
        slug=created.slug,
        is_active=created.is_active,
        tier=created.tier,
        created_at=created.created_at,
    )


@router.get(
    "",
    response_model=list[TenantResponse],
    summary="List All Tenants",
    dependencies=[Depends(require_permission(Permission.TENANTS_MANAGE))],
)
async def list_tenants(
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantResponse]:
    """List all registered multi-tenant organizations."""
    repo = SecurityRepository(session)
    tenants = await repo.list_tenants()
    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            slug=t.slug,
            is_active=t.is_active,
            tier=t.tier,
            created_at=t.created_at,
        )
        for t in tenants
    ]


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get Tenant by ID",
)
async def get_tenant(
    tenant_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantResponse:
    """Retrieve tenant details. Users can access their own tenant, platform admins can access any."""
    if (
        not ctx.is_platform_admin
        and ctx.tenant_id != tenant_id
        and not ctx.has_permission(Permission.TENANTS_MANAGE)
    ):
        raise ForbiddenException("Cannot access other tenant profiles")

    repo = SecurityRepository(session)
    tenant = await repo.get_tenant_by_id(tenant_id)
    if not tenant:
        raise EntityNotFoundException("Tenant", tenant_id)

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        is_active=tenant.is_active,
        tier=tenant.tier,
        created_at=tenant.created_at,
    )


@router.get(
    "/{tenant_id}/quotas",
    response_model=TenantQuotaResponse,
    summary="Get Tenant Resource Quotas",
)
async def get_tenant_quotas(
    tenant_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantQuotaResponse:
    """Retrieve rate limits and operational quotas for a tenant."""
    if (
        not ctx.is_platform_admin
        and ctx.tenant_id != tenant_id
        and not ctx.has_permission(Permission.QUOTAS_MANAGE)
    ):
        raise ForbiddenException("Cannot inspect quotas for other tenants")

    repo = SecurityRepository(session)
    quotas = await repo.get_tenant_quotas(tenant_id)
    if not quotas:
        raise EntityNotFoundException("TenantQuota", tenant_id)

    return TenantQuotaResponse(
        tenant_id=quotas.tenant_id,
        max_requests_per_minute=quotas.max_requests_per_minute,
        max_concurrent_simulations=quotas.max_concurrent_simulations,
        max_active_workflows=quotas.max_active_workflows,
        max_retention_days=quotas.max_retention_days,
    )


@router.put(
    "/{tenant_id}/quotas",
    response_model=TenantQuotaResponse,
    summary="Update Tenant Resource Quotas",
    dependencies=[Depends(require_permission(Permission.QUOTAS_MANAGE))],
)
async def update_tenant_quotas(
    tenant_id: str,
    req: TenantQuotaUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> TenantQuotaResponse:
    """Modify rate limit and simulation concurrency quotas for a tenant."""
    repo = SecurityRepository(session)
    existing = await repo.get_tenant_quotas(tenant_id)
    if not existing:
        raise EntityNotFoundException("Tenant", tenant_id)

    new_quotas = TenantQuotas(
        tenant_id=tenant_id,
        max_requests_per_minute=req.max_requests_per_minute or existing.max_requests_per_minute,
        max_concurrent_simulations=req.max_concurrent_simulations
        or existing.max_concurrent_simulations,
        max_active_workflows=req.max_active_workflows or existing.max_active_workflows,
        max_retention_days=req.max_retention_days or existing.max_retention_days,
    )

    updated = await repo.upsert_tenant_quotas(new_quotas)
    await session.commit()

    return TenantQuotaResponse(
        tenant_id=updated.tenant_id,
        max_requests_per_minute=updated.max_requests_per_minute,
        max_concurrent_simulations=updated.max_concurrent_simulations,
        max_active_workflows=updated.max_active_workflows,
        max_retention_days=updated.max_retention_days,
    )


@router.get(
    "/{tenant_id}/users",
    response_model=list[UserResponse],
    summary="List Users in Tenant",
    dependencies=[Depends(require_permission(Permission.USERS_MANAGE))],
)
async def list_tenant_users(
    tenant_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[UserResponse]:
    """List all user accounts belonging to a tenant organization."""
    if not ctx.is_platform_admin and ctx.tenant_id != tenant_id:
        raise ForbiddenException("Cannot manage users in other tenants")

    repo = SecurityRepository(session)
    users = await repo.list_users_for_tenant(tenant_id)
    return [
        UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            full_name=u.full_name,
            roles=u.roles or [],
            is_active=u.is_active,
            is_verified=u.is_verified,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.post(
    "/{tenant_id}/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User in Tenant",
    dependencies=[Depends(require_permission(Permission.USERS_MANAGE))],
)
async def create_tenant_user(
    tenant_id: str,
    req: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> UserResponse:
    """Provision a new user account within a tenant."""
    if not ctx.is_platform_admin and ctx.tenant_id != tenant_id:
        raise ForbiddenException("Cannot create users in other tenants")

    repo = SecurityRepository(session)
    tenant = await repo.get_tenant_by_id(tenant_id)
    if not tenant:
        raise EntityNotFoundException("Tenant", tenant_id)

    existing = await repo.get_user_by_email(req.email, tenant_id=tenant_id)
    if existing:
        raise ConflictException(f"User '{req.email}' already exists in tenant '{tenant_id}'")

    hashed_pw = hasher.hash_password(req.password)
    user_domain = User(
        id=f"usr_{uuid4().hex[:10]}",
        tenant_id=tenant_id,
        email=req.email,
        full_name=req.full_name,
        hashed_password=hashed_pw,
        roles=req.roles,
        is_active=True,
        is_verified=True,
    )

    created = await repo.create_user(user_domain)
    await session.commit()

    return UserResponse(
        id=created.id,
        tenant_id=created.tenant_id,
        email=created.email,
        full_name=created.full_name,
        roles=created.roles or [],
        is_active=created.is_active,
        is_verified=created.is_verified,
        created_at=created.created_at,
        last_login_at=created.last_login_at,
    )
