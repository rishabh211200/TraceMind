"""Zero-trust authentication, tenant isolation, and RBAC FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.exceptions import (
    AuthenticationException,
    ForbiddenException,
    RateLimitExceededException,
    TenantMismatchException,
)
from packages.common.security.context import set_current_tenant_context
from packages.common.security.crypto import hash_api_key_secret
from packages.common.security.jwt import (
    InvalidSignatureException,
    InvalidTokenException,
    JWTTokenManager,
    TokenExpiredException,
    TokenRevokedException,
    get_jwt_manager,
)
from packages.common.security.rate_limiter import (
    InMemorySlidingWindowRateLimiter,
    get_rate_limiter,
)
from packages.database.repositories.security_repository import SecurityRepository
from packages.database.session import get_db_session
from packages.domain.security import (
    ROLE_PERMISSIONS_MAP,
    Permission,
    Role,
    TenantContext,
)


def get_security_repo(session: AsyncSession = Depends(get_db_session)) -> SecurityRepository:
    """Dependency providing SecurityRepository instance."""
    return SecurityRepository(session)


async def get_tenant_context(  # noqa: C901
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),

    x_api_key: str | None = Header(None, alias="X-API-Key"),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-Id"),
    session: AsyncSession = Depends(get_db_session),
    jwt_mgr: JWTTokenManager = Depends(get_jwt_manager),
    rate_limiter: InMemorySlidingWindowRateLimiter = Depends(get_rate_limiter),
) -> TenantContext:
    """Authoritative tenant context resolver enforcing zero-trust, anti-spoofing, and rate limiting."""
    repo = SecurityRepository(session)
    ctx: TenantContext | None = None

    # 1. Bearer Token Authentication (Primary)
    if authorization and authorization.startswith("Bearer "):
        token_str = authorization[7:].strip()
        try:
            payload = jwt_mgr.decode_and_verify(token_str, expected_type="access")
            jti = payload.get("jti")
            if jti:
                is_revoked = await repo.is_token_revoked(jti)
                if is_revoked:
                    raise TokenRevokedException(f"Token '{jti}' is revoked")

            roles = [Role(r) for r in payload.get("roles", []) if r in Role._value2member_map_]
            if not roles:
                roles = [Role.VIEWER]

            perms: set[Permission] = set()
            for p_str in payload.get("permissions", []):
                if p_str in Permission._value2member_map_:
                    perms.add(Permission(p_str))
            # Also add default role permissions
            for r in roles:
                perms.update(ROLE_PERMISSIONS_MAP.get(r, set()))

            is_plat_admin = Role.PLATFORM_ADMIN in roles

            ctx = TenantContext(
                tenant_id=payload.get("tenant_id", "tenant_system"),
                user_id=payload.get("sub", "usr_anonymous"),
                email=payload.get("email", "user@tracemind.internal"),
                roles=roles,
                permissions=perms,
                is_authenticated=True,
                is_platform_admin=is_plat_admin,
            )
        except TokenExpiredException as e:
            raise AuthenticationException(f"Access token expired: {e}", error_code="TOKEN_EXPIRED") from e
        except InvalidSignatureException as e:
            raise AuthenticationException("Invalid RS256 token signature", error_code="INVALID_SIGNATURE") from e
        except TokenRevokedException as e:
            raise AuthenticationException(f"Token has been revoked: {e}", error_code="TOKEN_REVOKED") from e
        except InvalidTokenException as e:
            raise AuthenticationException(f"Invalid authentication token: {e}", error_code="INVALID_TOKEN") from e
        except Exception as e:
            raise AuthenticationException(f"Authentication failed: {e}", error_code="AUTH_FAILED") from e

    # 2. API Key Authentication (Secondary)
    elif x_api_key:
        try:
            # Expected format: tm_live_<prefix>_<secret> or tm_<prefix>_<secret>
            if x_api_key.startswith("tm_live_") or x_api_key.startswith("tm_test_"):
                prefix_hex = x_api_key[8:16]
                prefix = f"tm_{prefix_hex}"
                secret_raw = x_api_key[17:]
            else:
                parts = x_api_key.split("_", 2)
                prefix = f"tm_{parts[0]}" if len(parts) > 1 else x_api_key[:7]
                secret_raw = parts[-1] if len(parts) > 1 else x_api_key[7:]


            matching_keys = await repo.get_api_keys_by_prefix(prefix)
            valid_key = None
            hashed_input = hash_api_key_secret(secret_raw)

            for candidate in matching_keys:
                if candidate.hashed_secret == hashed_input:
                    if candidate.expires_at and candidate.expires_at < datetime.now(UTC):
                        continue
                    valid_key = candidate
                    break

            if not valid_key:
                raise AuthenticationException("Invalid or expired API key", error_code="INVALID_API_KEY")

            scopes = set()
            for s in valid_key.scopes or []:
                if isinstance(s, str) and s in Permission._value2member_map_:
                    scopes.add(Permission(s))
                elif isinstance(s, Permission):
                    scopes.add(s)

            user = await repo.get_user_by_id(valid_key.user_id) if valid_key.user_id else None
            roles = [Role(r) for r in (user.roles if user else ["OPERATOR"]) if r in Role._value2member_map_]
            for r in roles:
                scopes.update(ROLE_PERMISSIONS_MAP.get(r, set()))

            ctx = TenantContext(
                tenant_id=valid_key.tenant_id,
                user_id=valid_key.user_id or f"key_{valid_key.id}",
                email=user.email if user else "apikey@tracemind.internal",
                roles=roles,
                permissions=scopes,
                is_authenticated=True,
                is_platform_admin=Role.PLATFORM_ADMIN in roles,
            )
        except AuthenticationException:
            raise
        except Exception as e:
            raise AuthenticationException(f"API key authentication error: {e}", error_code="API_KEY_ERROR") from e

    # 3. Unauthenticated Fallback (Fail-Closed or System Tenant for Open Read routes)
    else:
        # Default unauthenticated anonymous viewer context
        ctx = TenantContext(
            tenant_id="tenant_system",
            user_id="usr_anonymous",
            email="anonymous@tracemind.internal",
            roles=[Role.VIEWER],
            permissions=set(ROLE_PERMISSIONS_MAP.get(Role.VIEWER, set())),
            is_authenticated=False,
            is_platform_admin=False,
        )

    # 4. Anti-Spoofing Validation for X-Tenant-Id Header
    if x_tenant_id and x_tenant_id.strip():
        claimed_tenant = x_tenant_id.strip()
        if ctx.is_authenticated:
            if claimed_tenant != ctx.tenant_id:
                if not ctx.is_platform_admin:
                    raise TenantMismatchException(
                        f"Tenant isolation mismatch: X-Tenant-Id '{claimed_tenant}' does not match authenticated token tenant '{ctx.tenant_id}'"
                    )
                else:
                    # Platform admin explicitly scoping into another tenant
                    ctx.tenant_id = claimed_tenant
        else:
            # Unauthenticated requests cannot claim other tenants
            ctx.tenant_id = claimed_tenant

    # 5. Sliding-Window Rate Limiting Check
    quotas = await repo.get_tenant_quotas(ctx.tenant_id)
    rpm_limit = quotas.max_requests_per_minute if quotas else 1200
    rate_result = await rate_limiter.check(f"tenant:{ctx.tenant_id}", max_requests=rpm_limit)
    if not rate_result.allowed:
        raise RateLimitExceededException(
            detail=f"Rate limit of {rpm_limit} requests/minute exceeded for tenant '{ctx.tenant_id}'.",
            retry_after=rate_result.retry_after,
        )

    # Propagate context variable for downstream workers/repositories
    set_current_tenant_context(ctx)
    return ctx


def require_authenticated() -> Callable[..., Any]:
    """Dependency enforcing that the request is authenticated with a valid JWT or API Key."""

    async def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not ctx.is_authenticated:
            raise AuthenticationException("Authentication credentials required for this endpoint.")
        return ctx

    return _dependency


def require_permission(*required_perms: Permission) -> Callable[..., Any]:
    """Dependency factory enforcing that the user has all specified permissions."""

    async def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not ctx.is_authenticated:
            raise AuthenticationException("Authentication credentials required.")
        for perm in required_perms:
            if not ctx.has_permission(perm):
                raise ForbiddenException(
                    f"Permission denied: missing required permission '{perm.value}'"
                )
        return ctx

    return _dependency


def require_role(*required_roles: Role) -> Callable[..., Any]:
    """Dependency factory enforcing that the user possesses at least one of the specified roles."""

    async def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not ctx.is_authenticated:
            raise AuthenticationException("Authentication credentials required.")
        if ctx.is_platform_admin:
            return ctx
        if not any(r in ctx.roles for r in required_roles):
            allowed = [r.value for r in required_roles]
            raise ForbiddenException(f"Role denied: requires one of {allowed}")
        return ctx

    return _dependency
