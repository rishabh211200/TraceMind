"""Domain models and value objects for Enterprise Multi-Tenancy and Zero-Trust Security."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    """Hierarchical Role-Based Access Control roles."""

    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    AUDITOR = "AUDITOR"
    VIEWER = "VIEWER"


class Permission(StrEnum):
    """Fine-grained permission identifiers mapped to protected platform actions."""

    # Tenant & User Management
    TENANTS_MANAGE = "tenants:manage"
    QUOTAS_MANAGE = "quotas:manage"
    USERS_MANAGE = "users:manage"
    API_KEYS_MANAGE = "api_keys:manage"
    AUTH_LOGOUT = "auth:logout"
    AUTH_ME = "auth:me"

    # Workflows & Topologies
    WORKFLOWS_READ = "workflows:read"
    WORKFLOWS_WRITE = "workflows:write"
    SERVICES_READ = "services:read"
    SERVICES_WRITE = "services:write"

    # Traces & Executions
    TRACES_READ = "traces:read"

    # Simulator & Chaos
    SIMULATOR_READ = "simulator:read"
    SIMULATOR_EXECUTE = "simulator:execute"
    CHAOS_INJECT = "chaos:inject"

    # ML Intelligence & Anomaly
    PREDICTIONS_EXECUTE = "predictions:execute"
    ANOMALIES_READ = "anomalies:read"
    ANOMALIES_FEEDBACK = "anomalies:feedback"
    RCA_EXECUTE = "rca:execute"
    RCA_READ = "rca:read"
    OPTIMIZER_EXECUTE = "optimizer:execute"
    OPTIMIZER_READ = "optimizer:read"

    # Remediation Control Plane
    REMEDIATION_READ = "remediation:read"
    REMEDIATION_SYNTHESIZE = "remediation:synthesize"
    REMEDIATION_EXECUTE = "remediation:execute"
    REMEDIATION_ROLLBACK = "remediation:rollback"
    REMEDIATION_POLICY_ADMIN = "remediation:policy_admin"
    AUDIT_READ = "audit:read"
    AUDIT_VERIFY = "audit:verify"

    # AI Analyst
    ANALYST_EXECUTE = "analyst:execute"
    ANALYST_READ = "analyst:read"


# Mapping from Role to set of default granted permissions
ROLE_PERMISSIONS_MAP: dict[Role, set[Permission]] = {
    Role.PLATFORM_ADMIN: set(Permission),
    Role.TENANT_ADMIN: {
        Permission.QUOTAS_MANAGE,
        Permission.USERS_MANAGE,
        Permission.API_KEYS_MANAGE,
        Permission.AUTH_LOGOUT,
        Permission.AUTH_ME,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_WRITE,
        Permission.SERVICES_READ,
        Permission.SERVICES_WRITE,
        Permission.TRACES_READ,
        Permission.SIMULATOR_READ,
        Permission.SIMULATOR_EXECUTE,
        Permission.CHAOS_INJECT,
        Permission.PREDICTIONS_EXECUTE,
        Permission.ANOMALIES_READ,
        Permission.ANOMALIES_FEEDBACK,
        Permission.RCA_EXECUTE,
        Permission.RCA_READ,
        Permission.OPTIMIZER_EXECUTE,
        Permission.OPTIMIZER_READ,
        Permission.REMEDIATION_READ,
        Permission.REMEDIATION_SYNTHESIZE,
        Permission.REMEDIATION_EXECUTE,
        Permission.REMEDIATION_ROLLBACK,
        Permission.REMEDIATION_POLICY_ADMIN,
        Permission.AUDIT_READ,
        Permission.ANALYST_EXECUTE,
        Permission.ANALYST_READ,
    },
    Role.OPERATOR: {
        Permission.AUTH_LOGOUT,
        Permission.AUTH_ME,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_WRITE,
        Permission.SERVICES_READ,
        Permission.SERVICES_WRITE,
        Permission.TRACES_READ,
        Permission.SIMULATOR_READ,
        Permission.SIMULATOR_EXECUTE,
        Permission.CHAOS_INJECT,
        Permission.PREDICTIONS_EXECUTE,
        Permission.ANOMALIES_READ,
        Permission.ANOMALIES_FEEDBACK,
        Permission.RCA_EXECUTE,
        Permission.RCA_READ,
        Permission.OPTIMIZER_EXECUTE,
        Permission.OPTIMIZER_READ,
        Permission.REMEDIATION_READ,
        Permission.REMEDIATION_SYNTHESIZE,
        Permission.REMEDIATION_EXECUTE,
        Permission.REMEDIATION_ROLLBACK,
        Permission.AUDIT_READ,
        Permission.ANALYST_EXECUTE,
        Permission.ANALYST_READ,
    },
    Role.ANALYST: {
        Permission.AUTH_LOGOUT,
        Permission.AUTH_ME,
        Permission.WORKFLOWS_READ,
        Permission.SERVICES_READ,
        Permission.TRACES_READ,
        Permission.SIMULATOR_READ,
        Permission.PREDICTIONS_EXECUTE,
        Permission.ANOMALIES_READ,
        Permission.ANOMALIES_FEEDBACK,
        Permission.RCA_EXECUTE,
        Permission.RCA_READ,
        Permission.OPTIMIZER_EXECUTE,
        Permission.OPTIMIZER_READ,
        Permission.REMEDIATION_READ,
        Permission.REMEDIATION_SYNTHESIZE,
        Permission.ANALYST_EXECUTE,
        Permission.ANALYST_READ,
    },
    Role.AUDITOR: {
        Permission.AUTH_LOGOUT,
        Permission.AUTH_ME,
        Permission.WORKFLOWS_READ,
        Permission.SERVICES_READ,
        Permission.TRACES_READ,
        Permission.ANOMALIES_READ,
        Permission.RCA_READ,
        Permission.OPTIMIZER_READ,
        Permission.REMEDIATION_READ,
        Permission.AUDIT_READ,
        Permission.AUDIT_VERIFY,
        Permission.ANALYST_READ,
    },
    Role.VIEWER: {
        Permission.AUTH_LOGOUT,
        Permission.AUTH_ME,
        Permission.WORKFLOWS_READ,
        Permission.SERVICES_READ,
        Permission.TRACES_READ,
        Permission.SIMULATOR_READ,
        Permission.ANOMALIES_READ,
        Permission.RCA_READ,
        Permission.OPTIMIZER_READ,
        Permission.REMEDIATION_READ,
        Permission.ANALYST_READ,
    },
}


class Tenant(BaseModel):
    """Multi-tenant organization boundary definition."""

    id: str = Field(description="Unique tenant identifier (e.g. tenant_system, tenant_acme)")
    name: str = Field(description="Display organization name")
    slug: str = Field(description="URL-safe unique tenant slug")
    is_active: bool = Field(default=True)
    tier: str = Field(
        default="ENTERPRISE", description="Tenant subscription tier (STARTER, PRO, ENTERPRISE)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class User(BaseModel):
    """User account within a tenant organization."""

    id: str
    tenant_id: str
    email: str
    full_name: str = "System User"
    hashed_password: str = ""
    roles: list[Role] = Field(default_factory=lambda: [Role.VIEWER])
    is_active: bool = True
    is_verified: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = None

    def get_all_permissions(self) -> set[Permission]:
        """Aggregate all permissions across assigned roles."""
        perms: set[Permission] = set()
        for role in self.roles:
            perms.update(ROLE_PERMISSIONS_MAP.get(role, set()))
        return perms


class ApiKey(BaseModel):
    """Programmatic API credential scoped to a tenant and specific permissions."""

    id: str
    tenant_id: str
    user_id: str
    key_name: str
    key_prefix: str
    hashed_secret: str
    scopes: list[Permission] = Field(default_factory=list)
    is_active: bool = True
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TenantQuotas(BaseModel):
    """Resource limits and rate quotas enforced per tenant."""

    tenant_id: str
    max_requests_per_minute: int = Field(default=1200, ge=10)
    max_concurrent_simulations: int = Field(default=5, ge=1)
    max_active_workflows: int = Field(default=50, ge=1)
    max_retention_days: int = Field(default=90, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuthTokens(BaseModel):
    """JWT Access and Refresh token pair payload."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(default=900, description="Access token expiration in seconds (15m)")
    user_id: str
    tenant_id: str
    roles: list[str]
    permissions: list[str]


class TenantContext(BaseModel):
    """Immutable execution context extracted from authenticated token or API key."""

    tenant_id: str = "tenant_system"
    user_id: str = "usr_system"
    email: str = "system@tracemind.internal"
    roles: list[Role] = Field(default_factory=lambda: [Role.PLATFORM_ADMIN])
    permissions: set[Permission] = Field(default_factory=lambda: set(Permission))
    is_authenticated: bool = False

    is_platform_admin: bool = False

    def has_permission(self, perm: Permission) -> bool:
        """Determines if the active context possesses the requested permission."""
        if self.is_platform_admin or Role.PLATFORM_ADMIN in self.roles:
            return True
        return perm in self.permissions


class SecurityAuditLog(BaseModel):
    """Audit log entry for security and authentication events."""

    id: str
    tenant_id: str
    user_id: str | None
    event_type: str
    ip_address: str | None = None
    user_agent: str | None = None
    status: str = "SUCCESS"
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
