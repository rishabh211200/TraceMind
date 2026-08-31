"""SQLAlchemy ORM models for Autonomous Closed-Loop Remediation."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class RemediationPolicyModel(Base):
    """SQLAlchemy model for declarative remediation policies."""

    __tablename__ = "remediation_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="tenant_system", index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_definition_id: Mapped[str] = mapped_column(String(128), default="*", index=True)
    incident_category: Mapped[str] = mapped_column(String(128), default="*", index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="SUPERVISED")
    max_blast_radius: Mapped[float] = mapped_column(Float, default=0.25)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    verification_timeout_seconds: Mapped[int] = mapped_column(Integer, default=45)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RemediationActionPlanModel(Base):
    """SQLAlchemy model for remediation action plans."""

    __tablename__ = "remediation_action_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="tenant_system", index=True, nullable=False
    )
    policy_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    workflow_definition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    incident_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    trigger_rca_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="STAGED", index=True)
    target_service: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_parameters: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    blast_radius_pct: Mapped[float] = mapped_column(Float, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expected_savings: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    pre_actuation_state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    post_actuation_state_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_TYPE, nullable=True
    )
    health_baseline: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    post_health_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    safety_report: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    execution_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RemediationAuditLedgerModel(Base):
    """SQLAlchemy model for tamper-evident cryptographic audit ledger entries."""

    __tablename__ = "remediation_audit_ledger"

    entry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="tenant_system", index=True, nullable=False
    )
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
