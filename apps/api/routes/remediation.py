"""FastAPI router for Autonomous Closed-Loop Remediation & Policy-Governed Actuation."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.dependencies.security import (
    get_tenant_context,
    require_permission,
)
from apps.api.schemas.remediation import (
    AuditLedgerEntryResponse,
    AuditLedgerVerificationResponse,
    LiveMeshStateResponse,
    RemediationPlanExecuteRequest,
    RemediationPlanResponse,
    RemediationPlanSynthesizeRequest,
    RemediationPolicyCreate,
    RemediationPolicyResponse,
)
from apps.ml.remediation.actuators.in_memory import InMemoryRoutingActuator
from apps.ml.remediation.audit_ledger import CryptographicAuditLedger
from apps.ml.remediation.planner import RemediationActionPlanner
from apps.ml.remediation.policy_engine import RemediationPolicyEngine
from apps.ml.remediation.safety_guards import SafetyInvariantEvaluator
from apps.ml.remediation.verifier import PostActuationHealthVerifier
from apps.ml.root_cause import RootCauseReport
from packages.common.logging import get_logger
from packages.domain.remediation import (
    ActionPlanStatus,
    ExecutionMode,
    RemediationActionPlan,
    RemediationPolicy,
)
from packages.domain.security import Permission, TenantContext

logger = get_logger("tracemind.api.remediation")

router = APIRouter(prefix="/api/v1/remediations", tags=["Autonomous Remediation & Self-Healing"])

# Module Singletons for runtime state
_policy_engine = RemediationPolicyEngine(safety_evaluator=SafetyInvariantEvaluator())
_actuator = InMemoryRoutingActuator()
_audit_ledger = CryptographicAuditLedger()
_verifier = PostActuationHealthVerifier(actuator=_actuator, audit_ledger=_audit_ledger)
_planner = RemediationActionPlanner(policy_engine=_policy_engine)
_stored_plans: dict[str, RemediationActionPlan] = {}


def get_remediation_components() -> tuple[
    RemediationPolicyEngine,
    InMemoryRoutingActuator,
    CryptographicAuditLedger,
    PostActuationHealthVerifier,
    RemediationActionPlanner,
    dict[str, RemediationActionPlan],
]:
    """Exposes singleton runtime components for dependency injection and testing."""
    return _policy_engine, _actuator, _audit_ledger, _verifier, _planner, _stored_plans


# -------------------------------------------------------------------------
# Action Plans
# -------------------------------------------------------------------------


@router.post(
    "/plans/synthesize",
    response_model=RemediationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Synthesize remediation plan from incident diagnostics",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_SYNTHESIZE))],
)
async def synthesize_plan(
    req: RemediationPlanSynthesizeRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> RemediationPlanResponse:
    """Synthesizes a safety-evaluated remediation action plan from RCA and Pareto optimizations."""
    current_state = await _actuator.get_current_state()

    # Construct mock/wrapper RCA report
    rca_report = None
    if req.incident_category or req.root_cause_service:
        rca_report = RootCauseReport(
            id=f"rca-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            execution_id=req.incident_id or f"exec-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            workflow_definition_id=req.workflow_definition_id,
            culprit_service=req.root_cause_service or "customer-db",
            incident_category=req.incident_category or "DATABASE_IOPS_SATURATION",
            confidence=req.diagnostic_confidence,
            causal_path=[req.root_cause_service or "customer-db"],
            supporting_evidence=["Autonomous diagnostic report for remediation synthesis"],
            primary_hypothesis=None,  # type: ignore[arg-type]
            alternative_hypotheses=[],
        )

    plan = _planner.synthesize_plan_from_diagnostics(
        workflow_definition_id=req.workflow_definition_id,
        rca_report=rca_report,
        optimization_recommendation=None,
        current_mesh_state=current_state,
    )
    plan.tenant_id = ctx.tenant_id

    # Store plan in memory
    _stored_plans[plan.id] = plan

    # Log cryptographic audit entry
    _audit_ledger.append_entry(
        plan_id=plan.id,
        event_type="PLAN_SYNTHESIZED",
        actor=f"{ctx.user_id} (AUTONOMOUS_POLICY)"
        if plan.execution_mode == ExecutionMode.AUTONOMOUS
        else f"{ctx.user_id} (POLICY_ENGINE)",
        payload={
            "tenant_id": ctx.tenant_id,
            "workflow_id": plan.workflow_definition_id,
            "action_type": plan.action_type.value,
            "execution_mode": plan.execution_mode.value,
            "blast_radius": plan.blast_radius_pct,
            "is_safe": plan.safety_report.is_safe if plan.safety_report else False,
        },
    )

    # AUTONOMOUS execution trigger
    if (
        plan.execution_mode == ExecutionMode.AUTONOMOUS
        and plan.safety_report
        and plan.safety_report.is_safe
    ):
        logger.info("Executing autonomous closed-loop remediation plan", plan_id=plan.id)
        plan.status = ActionPlanStatus.EXECUTING
        plan.executed_at = datetime.now(UTC)

        act_res = await _actuator.actuate(plan)
        if act_res.success:
            plan.post_actuation_state_snapshot = act_res.post_state
            plan.status = ActionPlanStatus.ACTIVE_VERIFYING
            _audit_ledger.append_entry(
                plan_id=plan.id,
                event_type="ACTUATION_COMMITTED",
                actor="AUTONOMOUS_POLICY",
                payload={"post_state": act_res.post_state.model_dump(mode="json"), "tenant_id": ctx.tenant_id},
            )

            # Auto-trigger health verifier
            await _verifier.verify_and_monitor(plan)
            plan.completed_at = datetime.now(UTC)
        else:
            plan.status = ActionPlanStatus.FAILED
            plan.execution_error = act_res.message
            _audit_ledger.append_entry(
                plan_id=plan.id,
                event_type="ACTUATION_FAILED",
                actor="AUTONOMOUS_POLICY",
                payload={"error": act_res.message, "tenant_id": ctx.tenant_id},
            )

    return RemediationPlanResponse.model_validate(plan)


@router.get(
    "/plans",
    response_model=list[RemediationPlanResponse],
    summary="List all synthesized remediation plans",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_READ))],
)
async def list_plans(
    workflow_definition_id: str | None = Query(None),
    status: ActionPlanStatus | None = Query(None),
    mode: ExecutionMode | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[RemediationPlanResponse]:
    """Lists remediation action plans with filtering."""
    results = [p for p in _stored_plans.values() if ctx.is_platform_admin or getattr(p, "tenant_id", "tenant_system") == ctx.tenant_id]
    if workflow_definition_id:
        results = [p for p in results if p.workflow_definition_id == workflow_definition_id]
    if status:
        results = [p for p in results if p.status == status]
    if mode:
        results = [p for p in results if p.execution_mode == mode]

    results.sort(key=lambda p: p.created_at, reverse=True)
    return [RemediationPlanResponse.model_validate(p) for p in results[:limit]]


@router.get(
    "/plans/{plan_id}",
    response_model=RemediationPlanResponse,
    summary="Get single remediation plan details",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_READ))],
)
async def get_plan(
    plan_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
) -> RemediationPlanResponse:
    """Retrieve single remediation action plan by identifier."""
    if plan_id not in _stored_plans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found",
        )
    plan = _stored_plans[plan_id]
    if not ctx.is_platform_admin and getattr(plan, "tenant_id", "tenant_system") != ctx.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found",
        )
    return RemediationPlanResponse.model_validate(plan)


@router.post(
    "/plans/{plan_id}/execute",
    response_model=RemediationPlanResponse,
    summary="Authorize and execute a staged remediation plan (Idempotent & Concurrency-Safe)",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_EXECUTE))],
)
async def execute_plan(
    plan_id: str,
    req: RemediationPlanExecuteRequest | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
) -> RemediationPlanResponse:
    """Authorizes and executes a staged or supervised remediation plan."""
    if plan_id not in _stored_plans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found",
        )

    plan = _stored_plans[plan_id]
    if not ctx.is_platform_admin and getattr(plan, "tenant_id", "tenant_system") != ctx.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found",
        )

    # Idempotency guard: if already succeeded or verifying, return cached state
    if plan.status in (ActionPlanStatus.SUCCEEDED, ActionPlanStatus.ACTIVE_VERIFYING):
        logger.info(
            "Idempotent execute request for completed/active plan",
            plan_id=plan.id,
            status=plan.status.value,
        )
        return RemediationPlanResponse.model_validate(plan)

    # ADVISORY cannot be actuated
    if plan.execution_mode == ExecutionMode.ADVISORY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ADVISORY plans cannot be executed directly; they are informational only.",
        )

    # Non-bypassable M14 Safety Invariants: even with ADMIN role, unsafe plan cannot execute
    if plan.safety_report and not plan.safety_report.is_safe:
        reasons = getattr(plan.safety_report, "rejection_reasons", getattr(plan.safety_report, "violations", []))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"M14 Safety Guard Violation: Plan is deemed unsafe ({reasons}) and cannot be executed.",
        )


    plan.status = ActionPlanStatus.EXECUTING
    plan.executed_at = datetime.now(UTC)

    actor = f"{ctx.user_id} (OPERATOR_USER)"
    if req and req.operator_notes:
        actor = f"{ctx.user_id} (OPERATOR_USER): {req.operator_notes}"

    _audit_ledger.append_entry(
        plan_id=plan.id,
        event_type="OPERATOR_AUTHORIZED",
        actor=actor,
        payload={"notes": req.operator_notes if req else None, "tenant_id": ctx.tenant_id},
    )

    act_res = await _actuator.actuate(plan)
    if not act_res.success:
        plan.status = ActionPlanStatus.FAILED
        plan.execution_error = act_res.message
        _audit_ledger.append_entry(
            plan_id=plan.id,
            event_type="ACTUATION_FAILED",
            actor=actor,
            payload={"error": act_res.message, "tenant_id": ctx.tenant_id},
        )
        return RemediationPlanResponse.model_validate(plan)

    plan.post_actuation_state_snapshot = act_res.post_state
    plan.status = ActionPlanStatus.ACTIVE_VERIFYING

    _audit_ledger.append_entry(
        plan_id=plan.id,
        event_type="ACTUATION_COMMITTED",
        actor=actor,
        payload={"post_state": act_res.post_state.model_dump(mode="json"), "tenant_id": ctx.tenant_id},
    )

    # Trigger post-actuation verification
    sim_telemetry = req.simulated_post_telemetry if req else None
    await _verifier.verify_and_monitor(plan, observed_post_metrics=sim_telemetry)
    plan.completed_at = datetime.now(UTC)

    return RemediationPlanResponse.model_validate(plan)


@router.post(
    "/plans/{plan_id}/rollback",
    response_model=RemediationPlanResponse,
    summary="Manually trigger emergency rollback of a plan (Idempotent & Exact State)",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_ROLLBACK))],
)
async def rollback_plan(
    plan_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
) -> RemediationPlanResponse:
    """Manually triggers emergency verbatim rollback of an active or succeeded plan."""
    if plan_id not in _stored_plans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found",
        )

    plan = _stored_plans[plan_id]
    if not ctx.is_platform_admin and getattr(plan, "tenant_id", "tenant_system") != ctx.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found",
        )

    # Idempotent rollback check
    if plan.status == ActionPlanStatus.ROLLED_BACK:
        return RemediationPlanResponse.model_validate(plan)

    actor = f"{ctx.user_id} (OPERATOR_USER)"
    _audit_ledger.append_entry(
        plan_id=plan.id,
        event_type="MANUAL_ROLLBACK_REQUESTED",
        actor=actor,
        payload={"previous_status": plan.status.value, "tenant_id": ctx.tenant_id},
    )

    rollback_res = await _actuator.rollback(
        plan=plan,
        exact_snapshot=plan.pre_actuation_state_snapshot,
    )

    if rollback_res.success:
        plan.status = ActionPlanStatus.ROLLED_BACK
        plan.completed_at = datetime.now(UTC)
        _audit_ledger.append_entry(
            plan_id=plan.id,
            event_type="ROLLBACK_COMPLETED",
            actor=actor,
            payload={"restored_state": rollback_res.restored_state.model_dump(mode="json"), "tenant_id": ctx.tenant_id},
        )
    else:
        plan.execution_error = rollback_res.message
        _audit_ledger.append_entry(
            plan_id=plan.id,
            event_type="ROLLBACK_FAILED",
            actor=actor,
            payload={"error": rollback_res.message, "tenant_id": ctx.tenant_id},
        )

    return RemediationPlanResponse.model_validate(plan)


# -------------------------------------------------------------------------
# Policies
# -------------------------------------------------------------------------


@router.get(
    "/policies",
    response_model=list[RemediationPolicyResponse],
    summary="List all declarative remediation policies",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_READ))],
)
async def list_policies(
    active_only: bool = Query(True),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[RemediationPolicyResponse]:
    """Lists registered remediation policies."""
    policies = _policy_engine.list_policies(active_only=active_only)
    return [RemediationPolicyResponse.model_validate(p) for p in policies]


@router.post(
    "/policies",
    response_model=RemediationPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new declarative remediation policy",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_POLICY_ADMIN))],
)
async def create_policy(
    req: RemediationPolicyCreate,
    ctx: TenantContext = Depends(get_tenant_context),
) -> RemediationPolicyResponse:
    """Registers or updates a declarative remediation policy."""
    policy_id = f"pol-{req.action_type.value.lower()}-{req.incident_category.lower()}"
    policy = RemediationPolicy(
        id=policy_id,
        name=req.name,
        workflow_definition_id=req.workflow_definition_id,
        incident_category=req.incident_category,
        action_type=req.action_type,
        execution_mode=req.execution_mode,
        max_blast_radius=req.max_blast_radius,
        cooldown_seconds=req.cooldown_seconds,
        verification_timeout_seconds=req.verification_timeout_seconds,
    )
    _policy_engine.register_policy(policy)
    return RemediationPolicyResponse.model_validate(policy)


@router.delete(
    "/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate or remove a remediation policy",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_POLICY_ADMIN))],
)
async def delete_policy(
    policy_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
) -> None:
    """Deletes a policy by ID."""
    deleted = _policy_engine.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found",
        )


# -------------------------------------------------------------------------
# Cryptographic Audit Ledger & Mesh State
# -------------------------------------------------------------------------


@router.get(
    "/audit-ledger",
    response_model=list[AuditLedgerEntryResponse],
    summary="List cryptographic audit ledger entries",
    dependencies=[Depends(require_permission(Permission.AUDIT_READ))],
)
async def list_audit_ledger(
    plan_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[AuditLedgerEntryResponse]:
    """Lists tamper-evident cryptographic audit ledger records."""
    entries = _audit_ledger.list_entries(plan_id=plan_id, limit=limit)
    return [AuditLedgerEntryResponse.model_validate(e) for e in entries]


@router.get(
    "/audit-ledger/verify",
    response_model=AuditLedgerVerificationResponse,
    summary="Verify cryptographic SHA-256 audit chain integrity",
    dependencies=[Depends(require_permission(Permission.AUDIT_VERIFY))],
)
async def verify_audit_ledger(
    ctx: TenantContext = Depends(get_tenant_context),
) -> AuditLedgerVerificationResponse:
    """Verifies the complete cryptographic hash chain from genesis to head."""
    is_valid, msg = _audit_ledger.verify_chain_integrity()
    return AuditLedgerVerificationResponse(
        is_valid=is_valid,
        message=msg,
        total_entries=len(_audit_ledger._entries),
    )


@router.get(
    "/mesh-state",
    response_model=LiveMeshStateResponse,
    summary="Get active live mesh routing and circuit breaker state",
    dependencies=[Depends(require_permission(Permission.REMEDIATION_READ))],
)
async def get_mesh_state(
    ctx: TenantContext = Depends(get_tenant_context),
) -> LiveMeshStateResponse:
    """Returns active runtime routing weights, circuits, and throttles."""
    state = await _actuator.get_current_state()
    return LiveMeshStateResponse.model_validate(state.model_dump(mode="json"))

