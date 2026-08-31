"""Comprehensive Integration Tests for Milestone 15: Zero-Trust Security, RBAC Matrix, Tenant Isolation & Anti-Spoofing."""

import pytest
from httpx import AsyncClient

from packages.common.security.jwt import JWTTokenManager, get_jwt_manager
from packages.domain.remediation import (
    ActionPlanStatus,
    ActionType,
    ExecutionMode,
    RemediationActionPlan,
    SafetyCheckReport,
    StateSnapshot,
)
from packages.domain.security import Permission, Role


@pytest.fixture
def jwt_mgr() -> JWTTokenManager:
    return get_jwt_manager()



@pytest.fixture
def token_platform_admin(jwt_mgr: JWTTokenManager) -> str:
    return jwt_mgr.create_access_token(
        user_id="usr_admin",
        tenant_id="tenant_system",
        email="admin@tracemind.io",
        roles=[Role.PLATFORM_ADMIN],
        permissions=list(Permission),
    )



@pytest.fixture
def token_tenant_admin_a(jwt_mgr: JWTTokenManager) -> str:
    return jwt_mgr.create_access_token(
        user_id="usr_tenant_a_admin",
        tenant_id="tenant_alpha",
        email="admin@alpha.io",
        roles=[Role.TENANT_ADMIN],
        permissions=[
            Permission.WORKFLOWS_READ,
            Permission.WORKFLOWS_WRITE,
            Permission.TRACES_READ,
            Permission.USERS_MANAGE,
            Permission.API_KEYS_MANAGE,
        ],
    )


@pytest.fixture
def token_operator_a(jwt_mgr: JWTTokenManager) -> str:
    return jwt_mgr.create_access_token(
        user_id="usr_op_a",
        tenant_id="tenant_alpha",
        email="op@alpha.io",
        roles=[Role.OPERATOR],
        permissions=[
            Permission.WORKFLOWS_READ,
            Permission.TRACES_READ,
            Permission.REMEDIATION_READ,
            Permission.REMEDIATION_SYNTHESIZE,
            Permission.REMEDIATION_EXECUTE,
            Permission.REMEDIATION_ROLLBACK,
            Permission.SIMULATOR_EXECUTE,
        ],
    )


@pytest.fixture
def token_analyst_a(jwt_mgr: JWTTokenManager) -> str:
    return jwt_mgr.create_access_token(
        user_id="usr_an_a",
        tenant_id="tenant_alpha",
        email="analyst@alpha.io",
        roles=[Role.ANALYST],
        permissions=[
            Permission.WORKFLOWS_READ,
            Permission.TRACES_READ,
            Permission.PREDICTIONS_EXECUTE,
            Permission.ANOMALIES_READ,
            Permission.ANOMALIES_FEEDBACK,
            Permission.RCA_READ,
            Permission.RCA_EXECUTE,
            Permission.OPTIMIZER_READ,
            Permission.OPTIMIZER_EXECUTE,
            Permission.ANALYST_READ,
            Permission.ANALYST_EXECUTE,
            Permission.REMEDIATION_READ,
        ],
    )


@pytest.fixture
def token_viewer_a(jwt_mgr: JWTTokenManager) -> str:
    return jwt_mgr.create_access_token(
        user_id="usr_view_a",
        tenant_id="tenant_alpha",
        email="viewer@alpha.io",
        roles=[Role.VIEWER],
        permissions=[
            Permission.WORKFLOWS_READ,
            Permission.TRACES_READ,
            Permission.ANOMALIES_READ,
            Permission.RCA_READ,
            Permission.OPTIMIZER_READ,
            Permission.ANALYST_READ,
            Permission.REMEDIATION_READ,
            Permission.SERVICES_READ,
        ],
    )


@pytest.fixture
def token_viewer_b(jwt_mgr: JWTTokenManager) -> str:
    """Viewer in completely separate Tenant Beta."""
    return jwt_mgr.create_access_token(
        user_id="usr_view_b",
        tenant_id="tenant_beta",
        email="viewer@beta.io",
        roles=[Role.VIEWER],
        permissions=[
            Permission.WORKFLOWS_READ,
            Permission.TRACES_READ,
            Permission.SERVICES_READ,
        ],
    )



# -----------------------------------------------------------------------------
# 1. RBAC Authorization Matrix Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rbac_endpoint_protection(
    async_client: AsyncClient,
    token_viewer_a: str,
    token_analyst_a: str,
    token_operator_a: str,
    token_platform_admin: str,
):
    """Verifies that endpoints enforce granular permissions and reject unauthorized roles with 403."""
    client = async_client
    # Viewer attempting to create a workflow -> 403 Forbidden
    res = await client.post(
        "/api/v1/workflows",
        headers={"Authorization": f"Bearer {token_viewer_a}"},
        json={
            "id": "wf_forbidden",
            "name": "Forbidden WF",
            "nodes": [{"id": "a", "service": "auth-service", "operation": "auth"}],
            "edges": [],
        },
    )
    assert res.status_code == 403

    # Viewer attempting to synthesize remediation plan -> 403 Forbidden
    res = await client.post(
        "/api/v1/remediations/plans/synthesize",
        headers={"Authorization": f"Bearer {token_viewer_a}"},
        json={"workflow_definition_id": "order_fulfillment"},
    )
    assert res.status_code == 403

    # Viewer attempting to run simulator -> 403 Forbidden
    res = await client.post(
        "/api/v1/simulator/generate",
        headers={"Authorization": f"Bearer {token_viewer_a}"},
        json={"workflow_count": 5},
    )
    assert res.status_code == 403

    # Operator CAN synthesize plan
    res = await client.post(
        "/api/v1/remediations/plans/synthesize",
        headers={"Authorization": f"Bearer {token_operator_a}"},
        json={"workflow_definition_id": "order_fulfillment"},
    )
    assert res.status_code == 201
    synthesized = res.json()
    assert synthesized["tenant_id"] == "tenant_alpha"

    # Viewer CAN read remediation plans
    res = await client.get(
        "/api/v1/remediations/plans",
        headers={"Authorization": f"Bearer {token_viewer_a}"},
    )
    assert res.status_code == 200

    # Unauthenticated request -> 401 Unauthorized
    res = await client.get("/api/v1/remediations/plans", headers={"Authorization": ""})
    assert res.status_code == 401



# -----------------------------------------------------------------------------
# 2. Tenant Isolation & IDOR/BOLA Defense
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation_idor_defense(
    async_client: AsyncClient,
    token_operator_a: str,
    token_viewer_b: str,
    token_platform_admin: str,
):
    """Verifies that Tenant Beta cannot access, see, or mutate plans belonging to Tenant Alpha."""
    client = async_client
    # Tenant Alpha operator creates a plan
    res = await client.post(
        "/api/v1/remediations/plans/synthesize",
        headers={"Authorization": f"Bearer {token_operator_a}"},
        json={"workflow_definition_id": "order_fulfillment"},
    )
    assert res.status_code == 201
    plan_id = res.json()["id"]

    # Tenant Beta attempts to get Tenant Alpha's plan -> 404 Not Found (IDOR defense)
    res_b = await client.get(
        f"/api/v1/remediations/plans/{plan_id}",
        headers={"Authorization": f"Bearer {token_viewer_b}"},
    )
    assert res_b.status_code == 404

    # Tenant Beta listing plans does NOT include Tenant Alpha's plan
    res_list_b = await client.get(
        "/api/v1/remediations/plans",
        headers={"Authorization": f"Bearer {token_viewer_b}"},
    )
    assert res_list_b.status_code == 200
    plan_ids_b = [p["id"] for p in res_list_b.json()]
    assert plan_id not in plan_ids_b

    # Platform Admin CAN view across tenants
    res_admin = await client.get(
        f"/api/v1/remediations/plans/{plan_id}",
        headers={"Authorization": f"Bearer {token_platform_admin}"},
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["id"] == plan_id


# -----------------------------------------------------------------------------
# 3. X-Tenant-Id Anti-Spoofing Defense
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_x_tenant_id_anti_spoofing(
    async_client: AsyncClient,
    token_operator_a: str,
    token_platform_admin: str,
):
    """Verifies that non-admin clients sending mismatched X-Tenant-Id headers are rejected with 403."""
    client = async_client
    # Operator A has token with tenant_id='tenant_alpha'.
    # Attacker tries to inject 'X-Tenant-Id: tenant_beta' or 'tenant_system'
    res_spoof = await client.get(
        "/api/v1/remediations/plans",
        headers={
            "Authorization": f"Bearer {token_operator_a}",
            "X-Tenant-Id": "tenant_beta",
        },
    )
    # MUST fail with 403 Forbidden due to TenantMismatchException
    assert res_spoof.status_code == 403
    assert "Tenant context mismatch" in res_spoof.text or "403" in str(res_spoof.status_code)

    # Platform Admin CAN provide X-Tenant-Id to impersonate / scope context
    res_admin = await client.get(
        "/api/v1/remediations/plans",
        headers={
            "Authorization": f"Bearer {token_platform_admin}",
            "X-Tenant-Id": "tenant_alpha",
        },
    )
    assert res_admin.status_code == 200


# -----------------------------------------------------------------------------
# 4. Non-Bypassable M14 Remediation Safety Invariants
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_bypassable_m14_safety_shield(
    async_client: AsyncClient,
    token_platform_admin: str,
):
    """Verifies that even a PLATFORM_ADMIN cannot execute an unsafe remediation plan (M14 invariant)."""
    from apps.api.routes.remediation import _stored_plans

    # Artificially store an unsafe plan
    unsafe_plan = RemediationActionPlan(
        id="plan_unsafe_test",
        tenant_id="tenant_system",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.SUPERVISED,
        target_service="customer-db",
        blast_radius_pct=0.75,
        idempotency_key="idemp_unsafe_test_001",
        pre_actuation_state_snapshot=StateSnapshot(routing_weights={"customer-db": 1.0}),
        status=ActionPlanStatus.STAGED,
        safety_report=SafetyCheckReport(
            is_safe=False,
            blast_radius_passed=False,
            anti_flapping_passed=True,
            acyclicity_passed=True,
            capacity_headroom_passed=True,
            rejection_reasons=["Blast radius 75.0% exceeds max threshold of 30.0%"],
        ),
    )
    _stored_plans[unsafe_plan.id] = unsafe_plan

    client = async_client
    # Platform Admin tries to execute unsafe plan -> 400 Bad Request (Safety Guard Invariant)
    res = await client.post(
        f"/api/v1/remediations/plans/{unsafe_plan.id}/execute",
        headers={"Authorization": f"Bearer {token_platform_admin}"},
        json={"operator_notes": "Emergency override attempt"},
    )
    assert res.status_code == 400
    assert "M14 Safety Guard Violation" in res.text


# -----------------------------------------------------------------------------
# 5. Token Refresh & Revocation via REST Endpoints
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_refresh_rotation_and_revocation_endpoints(async_client: AsyncClient):
    """Verifies /api/v1/auth/refresh rotates tokens and rejects replayed or revoked tokens."""
    client = async_client
    # 0. Register new test user and login to get refresh token
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rot_user@test.io",
            "password": "SecurePassword#2026!",
            "full_name": "Rotation Test User",
            "tenant_id": "tenant_system",
        },
    )
    assert reg_res.status_code in (200, 201)

    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "rot_user@test.io",
            "password": "SecurePassword#2026!",
            "tenant_id": "tenant_system",
        },
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    refresh_tok = login_data["refresh_token"]

    # 1. Refresh succeeds

    res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
    )
    assert res.status_code == 200
    data = res.json()
    new_access = data["access_token"]
    new_refresh = data["refresh_token"]

    assert new_access is not None
    assert new_refresh != refresh_tok

    # 2. Replaying the old refresh token MUST fail (single-use rotation)
    res_replay = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
    )
    assert res_replay.status_code == 401

    # 3. Logging out with new refresh token revokes it
    res_logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_access}"},
        json={"refresh_token": new_refresh},
    )
    assert res_logout.status_code == 200

    # 4. Attempting to use the logged-out refresh token fails
    res_after_logout = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert res_after_logout.status_code == 401


# -----------------------------------------------------------------------------
# 6. API Key Authentication & Invalidation
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_lifecycle_and_authentication(
    async_client: AsyncClient,
    token_tenant_admin_a: str,
    token_viewer_a: str,
):
    """Verifies API key creation by admin, authentication via X-API-Key, and revocation."""
    client = async_client

    # 1. Viewer trying to create API key -> 403 Forbidden
    res_forbidden = await client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {token_viewer_a}"},
        json={"key_name": "Viewer Key", "scopes": ["traces:read"]},
    )
    assert res_forbidden.status_code == 403

    # 2. Tenant Admin creates API key
    res_create = await client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {token_tenant_admin_a}"},
        json={
            "key_name": "Integration Test Key",
            "scopes": ["traces:read", "workflows:read"],
        },
    )
    assert res_create.status_code == 201
    key_data = res_create.json()
    raw_api_key = key_data["full_key"]
    key_id = key_data["id"]

    # 3. Access endpoint using X-API-Key header (override default client Bearer token)
    res_auth = await client.get(
        "/api/v1/workflows",
        headers={"Authorization": "", "X-API-Key": raw_api_key},
    )
    assert res_auth.status_code == 200

    # 4. Revoke API key
    res_revoke = await client.delete(
        f"/api/v1/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {token_tenant_admin_a}"},
    )
    assert res_revoke.status_code == 200

    # 5. Access with revoked key -> 401 Unauthorized
    res_after_revocation = await client.get(
        "/api/v1/workflows",
        headers={"Authorization": "", "X-API-Key": raw_api_key},
    )
    assert res_after_revocation.status_code == 401



# -----------------------------------------------------------------------------
# 7. User & Tenant Administration Privilege Controls
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_and_user_administration_privileges(
    async_client: AsyncClient,
    token_operator_a: str,
    token_platform_admin: str,
):
    """Verifies that only authorized roles can manage tenants and provision users."""
    client = async_client

    # Operator cannot create tenants -> 403 Forbidden
    res_tenant_op = await client.post(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {token_operator_a}"},
        json={
            "name": "Gamma Corp",
            "slug": "gamma-corp",
            "tier": "enterprise",
        },
    )
    assert res_tenant_op.status_code == 403

    # Platform Admin CAN create tenants
    res_tenant_admin = await client.post(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {token_platform_admin}"},
        json={
            "name": "Gamma Corp",
            "slug": "gamma-corp",
            "tier": "enterprise",
        },
    )
    assert res_tenant_admin.status_code == 201
    created_id = res_tenant_admin.json()["id"]
    assert "gamma" in created_id

    # Operator cannot list all tenants -> 403 Forbidden
    res_list_op = await client.get(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {token_operator_a}"},
    )
    assert res_list_op.status_code == 403

    # Platform admin CAN list all tenants
    res_list_admin = await client.get(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {token_platform_admin}"},
    )
    assert res_list_admin.status_code == 200
    tenant_ids = [t["id"] for t in res_list_admin.json()]
    assert created_id in tenant_ids

