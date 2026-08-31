"""FastAPI routes for authentication, RS256 token issuance, single-use refresh rotation, and logout."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_jwt_manager,
    get_tenant_context,
)
from apps.api.exceptions import (
    AuthenticationException,
    ConflictException,
    EntityNotFoundException,
    ForbiddenException,
)
from apps.api.schemas.security import (
    CurrentUserResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenRevokeRequest,
    UserResponse,
)
from packages.common.security.crypto import PasswordHasher
from packages.common.security.jwt import (
    JWTTokenManager,
    TokenExpiredException,
    TokenRevokedException,
)
from packages.database.repositories.security_repository import SecurityRepository
from packages.database.session import get_db_session
from packages.domain.security import AuthTokens, Role, TenantContext, User

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Governance"])
hasher = PasswordHasher()


@router.post("/login", response_model=AuthTokens, summary="User Password Login")
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    jwt_mgr: JWTTokenManager = Depends(get_jwt_manager),
) -> AuthTokens:
    """Authenticate user with email and password, issuing RS256 access and refresh tokens."""
    repo = SecurityRepository(session)
    user_model = await repo.get_user_by_email(req.email, tenant_id=req.tenant_id)
    if not user_model:
        raise AuthenticationException("Invalid email or password", error_code="INVALID_CREDENTIALS")

    if not user_model.is_active:
        raise ForbiddenException(
            "User account is inactive. Please contact administrator.", error_code="ACCOUNT_INACTIVE"
        )

    if not hasher.verify_password(req.password, user_model.hashed_password):
        raise AuthenticationException("Invalid email or password", error_code="INVALID_CREDENTIALS")

    # Update last login timestamp
    await repo.update_last_login(user_model.id)
    await session.commit()

    domain_roles = [Role(r) for r in (user_model.roles or []) if r in Role._value2member_map_]
    user_domain = User(
        id=user_model.id,
        tenant_id=user_model.tenant_id,
        email=user_model.email,
        full_name=user_model.full_name,
        hashed_password=user_model.hashed_password,
        roles=domain_roles if domain_roles else [Role.VIEWER],
        is_active=user_model.is_active,
        is_verified=user_model.is_verified,
        created_at=user_model.created_at,
        last_login_at=user_model.last_login_at,
    )

    tokens = jwt_mgr.create_tokens_for_user(user_domain)
    return tokens


@router.post("/refresh", response_model=AuthTokens, summary="Rotate Refresh Token")
async def refresh_token(
    req: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session),
    jwt_mgr: JWTTokenManager = Depends(get_jwt_manager),
) -> AuthTokens:
    """Single-use refresh token rotation issuing new RS256 token pair and revoking old refresh JTI."""
    repo = SecurityRepository(session)

    try:
        payload = jwt_mgr.decode_and_verify(req.refresh_token, expected_type="refresh")
    except TokenExpiredException as e:
        raise AuthenticationException(
            f"Refresh token expired: {e}", error_code="REFRESH_TOKEN_EXPIRED"
        ) from e
    except TokenRevokedException as e:
        raise AuthenticationException(
            f"Refresh token has been revoked: {e}", error_code="REFRESH_TOKEN_REVOKED"
        ) from e
    except Exception as e:
        raise AuthenticationException(
            f"Invalid refresh token: {e}", error_code="INVALID_REFRESH_TOKEN"
        ) from e

    old_jti = payload.get("jti")
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    exp_ts = payload.get("exp", int(datetime.now(UTC).timestamp()) + 604800)

    if not old_jti or not user_id or not tenant_id:
        raise AuthenticationException(
            "Malformed refresh token claims", error_code="MALFORMED_CLAIMS"
        )

    # Check DB revocation blocklist
    if await repo.is_token_revoked(old_jti):
        raise AuthenticationException(
            "Refresh token has already been consumed or revoked", error_code="TOKEN_REVOKED"
        )

    # Revoke old refresh token JTI immediately (single-use rotation)
    jwt_mgr.revoke_jti(old_jti)
    await repo.revoke_token(
        jti=old_jti,
        tenant_id=tenant_id,
        user_id=user_id,
        expires_at=datetime.fromtimestamp(exp_ts, tz=UTC),
        reason="REFRESH_ROTATION",
    )

    # Fetch active user
    user_model = await repo.get_user_by_id(user_id)
    if not user_model or not user_model.is_active:
        await session.commit()
        raise AuthenticationException(
            "User account associated with token is inactive or deleted", error_code="USER_NOT_FOUND"
        )

    domain_roles = [Role(r) for r in (user_model.roles or []) if r in Role._value2member_map_]
    user_domain = User(
        id=user_model.id,
        tenant_id=user_model.tenant_id,
        email=user_model.email,
        full_name=user_model.full_name,
        hashed_password=user_model.hashed_password,
        roles=domain_roles if domain_roles else [Role.VIEWER],
        is_active=user_model.is_active,
        is_verified=user_model.is_verified,
        created_at=user_model.created_at,
        last_login_at=user_model.last_login_at,
    )

    new_tokens = jwt_mgr.create_tokens_for_user(user_domain)
    await session.commit()
    return new_tokens


@router.post("/logout", summary="Revoke Session & Tokens")
async def logout(
    req: TokenRevokeRequest | None = None,
    authorization: str | None = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
    jwt_mgr: JWTTokenManager = Depends(get_jwt_manager),
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Revoke active JWT access token and optional refresh token."""
    repo = SecurityRepository(session)

    # Revoke bearer token if present
    if authorization and authorization.startswith("Bearer "):
        token_str = authorization[7:].strip()
        try:
            payload = jwt_mgr.decode_and_verify(token_str)
            jti = payload.get("jti")
            exp_ts = payload.get("exp", int(datetime.now(UTC).timestamp()) + 900)
            if jti:
                jwt_mgr.revoke_jti(jti)
                await repo.revoke_token(
                    jti=jti,
                    tenant_id=ctx.tenant_id,
                    user_id=ctx.user_id,
                    expires_at=datetime.fromtimestamp(exp_ts, tz=UTC),
                    reason="USER_LOGOUT",
                )
        except Exception:
            pass  # Fail gracefully during logout

    # Revoke explicit refresh token or JTI if provided
    if req:
        if req.refresh_token:
            try:
                ref_payload = jwt_mgr.decode_and_verify(req.refresh_token, expected_type="refresh")
                ref_jti = ref_payload.get("jti")
                exp_ts = ref_payload.get("exp", int(datetime.now(UTC).timestamp()) + 604800)
                if ref_jti:
                    jwt_mgr.revoke_jti(ref_jti)
                    await repo.revoke_token(
                        jti=ref_jti,
                        tenant_id=ctx.tenant_id,
                        user_id=ctx.user_id,
                        expires_at=datetime.fromtimestamp(exp_ts, tz=UTC),
                        reason=req.reason,
                    )
            except Exception:
                pass
        elif req.jti:
            jwt_mgr.revoke_jti(req.jti)
            await repo.revoke_token(
                jti=req.jti,
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                expires_at=datetime.now(UTC),
                reason=req.reason,
            )

    await session.commit()
    return {"status": "success", "message": "Successfully logged out and revoked credentials"}


@router.get("/me", response_model=CurrentUserResponse, summary="Get Current Session Profile")
async def get_current_user_profile(
    ctx: TenantContext = Depends(get_tenant_context),
) -> CurrentUserResponse:
    """Retrieve identity, active tenant, roles, and evaluated permissions for the current caller."""
    return CurrentUserResponse(
        user_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        email=ctx.email,
        roles=[r.value if isinstance(r, Role) else str(r) for r in ctx.roles],
        permissions=[p.value if hasattr(p, "value") else str(p) for p in ctx.permissions],
        is_platform_admin=ctx.is_platform_admin,
        is_authenticated=ctx.is_authenticated,
    )


@router.post(
    "/register", response_model=UserResponse, summary="Self-Registration / User Provisioning"
)
async def register(
    req: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Register a new user in the specified tenant."""
    repo = SecurityRepository(session)

    # Verify tenant exists
    tenant = await repo.get_tenant_by_id(req.tenant_id)
    if not tenant:
        raise EntityNotFoundException("Tenant", req.tenant_id)

    # Check for existing email in tenant
    existing = await repo.get_user_by_email(req.email, tenant_id=req.tenant_id)
    if existing:
        raise ConflictException(
            f"User with email '{req.email}' already exists in tenant '{req.tenant_id}'"
        )

    hashed_pw = hasher.hash_password(req.password)
    user_domain = User(
        id=f"usr_{req.email.split('@')[0][:8]}_{req.tenant_id[:6]}",
        tenant_id=req.tenant_id,
        email=req.email,
        full_name=req.full_name,
        hashed_password=hashed_pw,
        roles=req.roles,
        is_active=True,
        is_verified=True,
    )

    created_model = await repo.create_user(user_domain)
    await session.commit()

    return UserResponse(
        id=created_model.id,
        tenant_id=created_model.tenant_id,
        email=created_model.email,
        full_name=created_model.full_name,
        roles=created_model.roles or [],
        is_active=created_model.is_active,
        is_verified=created_model.is_verified,
        created_at=created_model.created_at,
        last_login_at=created_model.last_login_at,
    )
