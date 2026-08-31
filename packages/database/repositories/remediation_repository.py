"""Async repository for querying and persisting remediation policies, plans, and audit entries."""

from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.remediation import (
    RemediationActionPlanModel,
    RemediationAuditLedgerModel,
    RemediationPolicyModel,
)
from packages.domain.remediation import (
    ActionPlanStatus,
    RemediationActionPlan,
    RemediationPolicy,
)


class RemediationRepository:
    """Async repository managing remediation policies, action plans, and cryptographic audit records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------------------
    # Policies
    # -------------------------------------------------------------------------

    async def get_policy(self, policy_id: str) -> RemediationPolicyModel | None:
        """Fetch policy by ID."""
        stmt = select(RemediationPolicyModel).where(RemediationPolicyModel.id == policy_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_policies(
        self,
        workflow_definition_id: str | None = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RemediationPolicyModel]:
        """List policies with optional workflow filter."""
        stmt = select(RemediationPolicyModel)
        if active_only:
            stmt = stmt.where(RemediationPolicyModel.is_active.is_(True))
        if workflow_definition_id:
            stmt = stmt.where(
                (RemediationPolicyModel.workflow_definition_id == workflow_definition_id)
                | (RemediationPolicyModel.workflow_definition_id == "*")
            )
        stmt = stmt.order_by(desc(RemediationPolicyModel.created_at)).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_policy(self, policy: RemediationPolicy) -> RemediationPolicyModel:
        """Insert or update a remediation policy."""
        existing = await self.get_policy(policy.id)
        if existing:
            existing.name = policy.name
            existing.workflow_definition_id = policy.workflow_definition_id
            existing.incident_category = policy.incident_category
            existing.action_type = policy.action_type.value
            existing.execution_mode = policy.execution_mode.value
            existing.max_blast_radius = policy.max_blast_radius
            existing.cooldown_seconds = policy.cooldown_seconds
            existing.verification_timeout_seconds = policy.verification_timeout_seconds
            existing.is_active = policy.is_active
            await self.session.flush()
            return existing

        record = RemediationPolicyModel(
            id=policy.id,
            name=policy.name,
            workflow_definition_id=policy.workflow_definition_id,
            incident_category=policy.incident_category,
            action_type=policy.action_type.value,
            execution_mode=policy.execution_mode.value,
            max_blast_radius=policy.max_blast_radius,
            cooldown_seconds=policy.cooldown_seconds,
            verification_timeout_seconds=policy.verification_timeout_seconds,
            is_active=policy.is_active,
            created_at=policy.created_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def delete_policy(self, policy_id: str) -> bool:
        """Deactivate or remove a policy."""
        stmt = delete(RemediationPolicyModel).where(RemediationPolicyModel.id == policy_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        rowcount = getattr(result, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    # -------------------------------------------------------------------------
    # Action Plans
    # -------------------------------------------------------------------------

    async def get_plan(self, plan_id: str) -> RemediationActionPlanModel | None:
        """Fetch remediation plan by ID."""
        stmt = select(RemediationActionPlanModel).where(RemediationActionPlanModel.id == plan_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_plan_by_idempotency_key(
        self, idempotency_key: str
    ) -> RemediationActionPlanModel | None:
        """Fetch remediation plan by unique idempotency key."""
        stmt = select(RemediationActionPlanModel).where(
            RemediationActionPlanModel.idempotency_key == idempotency_key
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_plan(self, plan: RemediationActionPlan) -> RemediationActionPlanModel:
        """Persist a new remediation action plan."""
        record = RemediationActionPlanModel(
            id=plan.id,
            policy_id=plan.policy_id,
            workflow_definition_id=plan.workflow_definition_id,
            incident_id=plan.incident_id,
            trigger_rca_id=plan.trigger_rca_id,
            action_type=plan.action_type.value,
            execution_mode=plan.execution_mode.value,
            status=plan.status.value,
            target_service=plan.target_service,
            target_parameters=plan.target_parameters,
            blast_radius_pct=plan.blast_radius_pct,
            idempotency_key=plan.idempotency_key,
            expected_savings=plan.expected_savings,
            pre_actuation_state_snapshot=plan.pre_actuation_state_snapshot.model_dump(mode="json"),
            post_actuation_state_snapshot=(
                plan.post_actuation_state_snapshot.model_dump(mode="json")
                if plan.post_actuation_state_snapshot
                else None
            ),
            health_baseline=plan.health_baseline,
            post_health_metrics=plan.post_health_metrics,
            safety_report=plan.safety_report.model_dump(mode="json")
            if plan.safety_report
            else None,
            execution_error=plan.execution_error,
            created_at=plan.created_at,
            executed_at=plan.executed_at,
            completed_at=plan.completed_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def update_plan_status(
        self,
        plan_id: str,
        status: ActionPlanStatus,
        executed_at: datetime | None = None,
        completed_at: datetime | None = None,
        post_state: dict[str, Any] | None = None,
        post_health_metrics: dict[str, Any] | None = None,
        execution_error: str | None = None,
    ) -> RemediationActionPlanModel | None:
        """Atomically update plan execution status and metrics."""
        values: dict[str, Any] = {"status": status.value}
        if executed_at is not None:
            values["executed_at"] = executed_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if post_state is not None:
            values["post_actuation_state_snapshot"] = post_state
        if post_health_metrics is not None:
            values["post_health_metrics"] = post_health_metrics
        if execution_error is not None:
            values["execution_error"] = execution_error

        stmt = (
            update(RemediationActionPlanModel)
            .where(RemediationActionPlanModel.id == plan_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_plan(plan_id)

    async def list_plans(
        self,
        workflow_definition_id: str | None = None,
        status: str | None = None,
        execution_mode: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RemediationActionPlanModel], int]:
        """List remediation plans with filtering and total count."""
        base_stmt = select(RemediationActionPlanModel)
        count_stmt = select(func.count()).select_from(RemediationActionPlanModel)

        if workflow_definition_id:
            base_stmt = base_stmt.where(
                RemediationActionPlanModel.workflow_definition_id == workflow_definition_id
            )
            count_stmt = count_stmt.where(
                RemediationActionPlanModel.workflow_definition_id == workflow_definition_id
            )
        if status:
            base_stmt = base_stmt.where(RemediationActionPlanModel.status == status)
            count_stmt = count_stmt.where(RemediationActionPlanModel.status == status)
        if execution_mode:
            base_stmt = base_stmt.where(RemediationActionPlanModel.execution_mode == execution_mode)
            count_stmt = count_stmt.where(
                RemediationActionPlanModel.execution_mode == execution_mode
            )

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = (
            base_stmt.order_by(desc(RemediationActionPlanModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        items = list(res.scalars().all())

        return items, total

    # -------------------------------------------------------------------------
    # Cryptographic Audit Ledger
    # -------------------------------------------------------------------------

    async def append_audit_entry(
        self,
        entry_id: str,
        plan_id: str,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        timestamp: datetime,
        previous_hash: str,
        entry_hash: str,
    ) -> RemediationAuditLedgerModel:
        """Persist a cryptographic audit ledger entry."""
        record = RemediationAuditLedgerModel(
            entry_id=entry_id,
            plan_id=plan_id,
            event_type=event_type,
            actor=actor,
            payload=payload,
            timestamp=timestamp,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_audit_entries(
        self,
        plan_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[RemediationAuditLedgerModel], int]:
        """List audit ledger records in chronological order."""
        base_stmt = select(RemediationAuditLedgerModel)
        count_stmt = select(func.count()).select_from(RemediationAuditLedgerModel)

        if plan_id:
            base_stmt = base_stmt.where(RemediationAuditLedgerModel.plan_id == plan_id)
            count_stmt = count_stmt.where(RemediationAuditLedgerModel.plan_id == plan_id)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = (
            base_stmt.order_by(RemediationAuditLedgerModel.timestamp.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total
