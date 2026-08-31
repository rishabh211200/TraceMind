"""003 Multi-Tenant Isolation and Zero-Trust Security Schema.

Revision ID: 003_multitenant_security_schema
Revises: 002_analyst_tables
Create Date: 2026-08-31 12:00:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_multitenant_security_schema"
down_revision: str | None = "002_analyst_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create Tenants Table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tier", sa.String(length=32), nullable=False, server_default="ENTERPRISE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_tenants_id", "tenants", ["id"])
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    # 2. Create Users Table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # 3. Create API Keys Table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("key_name", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("hashed_secret", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"])
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])

    # 4. Create Revoked Tokens Table
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("jti", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False, server_default="LOGOUT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti"),
    )
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"])
    op.create_index("ix_revoked_tokens_tenant_id", "revoked_tokens", ["tenant_id"])

    # 5. Create Tenant Quotas Table
    op.create_table(
        "tenant_quotas",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("max_requests_per_minute", sa.Integer(), nullable=False, server_default="1200"),
        sa.Column("max_concurrent_simulations", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_active_workflows", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("max_retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.create_index("ix_tenant_quotas_tenant_id", "tenant_quotas", ["tenant_id"])

    # 6. Seed Default System Tenant
    tenants_table = sa.table(
        "tenants",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("tier", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        tenants_table,
        [
            {
                "id": "tenant_system",
                "name": "TraceMind Default Organization",
                "slug": "tracemind-default",
                "is_active": True,
                "tier": "ENTERPRISE",
                "created_at": now,
            }
        ],
    )

    # 7. Add tenant_id column with backfill default to all existing M0-M14 tables
    tenant_scoped_tables = [
        "services",
        "workflow_definitions",
        "workflow_executions",
        "trace_events",
        "incidents",
        "predictions",
        "anomalies",
        "root_causes",
        "optimizations",
        "analyst_conversations",
        "remediation_policies",
        "remediation_action_plans",
        "remediation_audit_ledger",
    ]

    for table_name in tenant_scoped_tables:
        op.add_column(
            table_name,
            sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="tenant_system"),
        )
        op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])


def downgrade() -> None:
    tenant_scoped_tables = [
        "remediation_audit_ledger",
        "remediation_action_plans",
        "remediation_policies",
        "analyst_conversations",
        "optimizations",
        "root_causes",
        "anomalies",
        "predictions",
        "incidents",
        "trace_events",
        "workflow_executions",
        "workflow_definitions",
        "services",
    ]
    for table_name in tenant_scoped_tables:
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        op.drop_column(table_name, "tenant_id")

    op.drop_table("tenant_quotas")
    op.drop_table("revoked_tokens")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("tenants")
