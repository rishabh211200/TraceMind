"""FastAPI routes for tenant-scoped programmatic API key generation, listing, and revocation."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
    require_permission,
)
from apps.api.exceptions import EntityNotFoundException
from apps.api.schemas.security import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
)
from packages.common.security.crypto import generate_api_key
from packages.database.repositories.security_repository import SecurityRepository
from packages.database.session import get_db_session
from packages.domain.security import ApiKey, Permission, TenantContext

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys & Programmatic Access"])


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate New API Key",
    dependencies=[Depends(require_permission(Permission.API_KEYS_MANAGE))],
)
async def create_api_key(
    req: ApiKeyCreate,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ApiKeyCreatedResponse:
    """Generate a high-entropy API key. The unhashed raw key is returned ONLY once in this response."""
    repo = SecurityRepository(session)
    full_key, prefix, hashed_secret = generate_api_key(ctx.tenant_id, req.key_name)

    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=req.expires_in_days)

    domain_key = ApiKey(
        id=f"key_{uuid4().hex[:10]}",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        key_name=req.key_name,
        key_prefix=prefix,
        hashed_secret=hashed_secret,
        scopes=req.scopes,
        is_active=True,
        expires_at=expires_at,
    )

    created = await repo.create_api_key(domain_key)
    await session.commit()

    return ApiKeyCreatedResponse(
        id=created.id,
        tenant_id=created.tenant_id,
        user_id=created.user_id,
        key_name=created.key_name,
        key_prefix=created.key_prefix,
        scopes=created.scopes or [],
        is_active=created.is_active,
        expires_at=created.expires_at,
        created_at=created.created_at,
        full_key=full_key,
    )


@router.get(
    "",
    response_model=list[ApiKeyResponse],
    summary="List Active API Keys",
    dependencies=[Depends(require_permission(Permission.API_KEYS_MANAGE))],
)
async def list_api_keys(
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[ApiKeyResponse]:
    """List all API keys belonging to the caller's tenant organization (secrets redacted)."""
    repo = SecurityRepository(session)
    keys = await repo.list_api_keys_for_tenant(ctx.tenant_id)
    return [
        ApiKeyResponse(
            id=k.id,
            tenant_id=k.tenant_id,
            user_id=k.user_id,
            key_name=k.key_name,
            key_prefix=k.key_prefix,
            scopes=k.scopes or [],
            is_active=k.is_active,
            expires_at=k.expires_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete(
    "/{key_id}",
    summary="Revoke API Key",
    dependencies=[Depends(require_permission(Permission.API_KEYS_MANAGE))],
)
async def revoke_api_key(
    key_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Permanently deactivate an API key."""
    repo = SecurityRepository(session)
    success = await repo.revoke_api_key(key_id, tenant_id=ctx.tenant_id)
    if not success:
        raise EntityNotFoundException("ApiKey", key_id)

    await session.commit()
    return {"status": "success", "message": f"API key '{key_id}' revoked successfully"}
