"""Unit tests for Milestone 14 Autonomous Closed-Loop Remediation & Safety Invariant Engine."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.ml.remediation.actuators.in_memory import InMemoryRoutingActuator
from apps.ml.remediation.audit_ledger import CryptographicAuditLedger
from apps.ml.remediation.planner import RemediationActionPlanner
from apps.ml.remediation.policy_engine import RemediationPolicyEngine
from apps.ml.remediation.safety_guards import SafetyInvariantEvaluator
from apps.ml.remediation.verifier import PostActuationHealthVerifier
from packages.domain.remediation import (
    ActionPlanStatus,
    ActionType,
    ExecutionMode,
    RemediationActionPlan,
    StateSnapshot,
)


@pytest.fixture
def initial_snapshot() -> StateSnapshot:
    """Fixture providing a clean baseline service mesh state snapshot."""
    return StateSnapshot(
        routing_weights={"path_01": 1.0, "path_02": 0.0},
        circuit_states={"customer-db": "CLOSED", "payment-service": "CLOSED"},
        concurrency_limits={"customer-db": 100, "payment-service": 80},
        retry_multipliers={"customer-db": 1.0, "payment-service": 1.0},
    )


@pytest.fixture
def safety_evaluator() -> SafetyInvariantEvaluator:
    return SafetyInvariantEvaluator(max_blast_radius=0.30, default_cooldown_seconds=300)


@pytest.fixture
def policy_engine(safety_evaluator: SafetyInvariantEvaluator) -> RemediationPolicyEngine:
    return RemediationPolicyEngine(safety_evaluator=safety_evaluator)


@pytest.fixture
def planner(policy_engine: RemediationPolicyEngine) -> RemediationActionPlanner:
    return RemediationActionPlanner(policy_engine=policy_engine)


@pytest.mark.asyncio
async def test_blast_radius_rejection(
    safety_evaluator: SafetyInvariantEvaluator, initial_snapshot: StateSnapshot
):
    """Asserts that plans with blast radius > 30% or throttle > 25% are rejected."""
    # 1. Blast radius > 30%
    unsafe_plan = RemediationActionPlan(
        id="plan-unsafe-blast",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.AUTONOMOUS,
        target_service="customer-db",
        blast_radius_pct=0.45,  # Exceeds 30%
        idempotency_key="key-001",
        pre_actuation_state_snapshot=initial_snapshot,
    )
    is_ok, msg = safety_evaluator.validate_blast_radius(unsafe_plan)
    assert not is_ok
    assert "exceeds maximum permitted" in msg

    # 2. Concurrency throttle > 25%
    unsafe_throttle_plan = RemediationActionPlan(
        id="plan-unsafe-throttle",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.CONCURRENCY_THROTTLE,
        execution_mode=ExecutionMode.SUPERVISED,
        target_service="customer-db",
        target_parameters={"throttle_percentage": 0.35},
        blast_radius_pct=0.20,
        idempotency_key="key-002",
        pre_actuation_state_snapshot=initial_snapshot,
    )
    is_ok, msg = safety_evaluator.validate_blast_radius(unsafe_throttle_plan)
    assert not is_ok
    assert "Throttle percentage 35.0% exceeds" in msg


@pytest.mark.asyncio
async def test_anti_flapping_cooldown_rejection(
    safety_evaluator: SafetyInvariantEvaluator, initial_snapshot: StateSnapshot
):
    """Asserts that components modified within cooldown period are rejected."""
    plan = RemediationActionPlan(
        id="plan-flapping",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.AUTONOMOUS,
        target_service="customer-db",
        blast_radius_pct=0.20,
        idempotency_key="key-003",
        pre_actuation_state_snapshot=initial_snapshot,
    )

    history = [
        {
            "target_service": "customer-db",
            "workflow_definition_id": "order_fulfillment",
            "executed_at": datetime.now(UTC) - timedelta(seconds=60),  # 60s ago < 300s
        }
    ]

    is_ok, msg = safety_evaluator.validate_anti_flapping(plan, history, cooldown_seconds=300)
    assert not is_ok
    assert "within cooldown period" in msg


@pytest.mark.asyncio
async def test_acyclicity_and_culprit_rejection(
    safety_evaluator: SafetyInvariantEvaluator, initial_snapshot: StateSnapshot
):
    """Asserts that alternative diversion routes containing the root culprit are rejected."""
    plan = RemediationActionPlan(
        id="plan-cycle",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.AUTONOMOUS,
        target_service="customer-db",
        blast_radius_pct=0.20,
        idempotency_key="key-004",
        pre_actuation_state_snapshot=initial_snapshot,
    )

    # Culprit is customer-db; target path contains customer-db
    is_ok, msg = safety_evaluator.validate_dependency_acyclicity(
        plan,
        root_cause_culprit="customer-db",
        target_path_services=["customer-service", "customer-db"],  # Contains culprit
    )
    assert not is_ok
    assert "contains active root culprit" in msg


@pytest.mark.asyncio
async def test_capacity_headroom_rejection(
    safety_evaluator: SafetyInvariantEvaluator, initial_snapshot: StateSnapshot
):
    """Asserts that diversion paths without sufficient spare capacity are rejected."""
    plan = RemediationActionPlan(
        id="plan-headroom",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.AUTONOMOUS,
        target_service="customer-db",
        target_parameters={"traffic_shift_pct": 0.25},
        blast_radius_pct=0.25,
        idempotency_key="key-005",
        pre_actuation_state_snapshot=initial_snapshot,
    )

    is_ok, msg = safety_evaluator.validate_capacity_headroom(
        plan,
        target_path_spare_capacity_ratio=0.20,  # Below 40% threshold
    )
    assert not is_ok
    assert "below safety threshold" in msg


@pytest.mark.asyncio
async def test_in_memory_actuator_atomic_mutations_and_exact_rollback(
    initial_snapshot: StateSnapshot,
):
    """Asserts atomic actuation, idempotency, and verbatim exact-state rollback restoration."""
    actuator = InMemoryRoutingActuator(initial_state=initial_snapshot)

    plan = RemediationActionPlan(
        id="plan-actuate-01",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.AUTONOMOUS,
        target_service="customer-db",
        target_parameters={
            "source_path_id": "path_01",
            "target_path_id": "path_02",
            "traffic_shift_pct": 0.25,
        },
        blast_radius_pct=0.25,
        idempotency_key="key-006",
        pre_actuation_state_snapshot=initial_snapshot,
    )

    # 1. Actuate Plan
    res = await actuator.actuate(plan)
    assert res.success
    assert res.post_state.routing_weights["path_01"] == 0.75
    assert res.post_state.routing_weights["path_02"] == 0.25
    assert not res.is_idempotent_replay

    # 2. Test Idempotency Guard (Concurrent / Repeated Request)
    dup_res = await actuator.actuate(plan)
    assert dup_res.success
    assert dup_res.is_idempotent_replay
    assert (
        dup_res.post_state.routing_weights["path_01"] == 0.75
    )  # Still 0.75, not decremented twice!

    # 3. Verbatim Exact-State Rollback Restoration
    rb_res = await actuator.rollback(plan, exact_snapshot=initial_snapshot)
    assert rb_res.success
    assert rb_res.restored_state.routing_weights["path_01"] == 1.0
    assert rb_res.restored_state.routing_weights["path_02"] == 0.0
    assert rb_res.restored_state.circuit_states == initial_snapshot.circuit_states

    # 4. Idempotent Rollback Guard
    dup_rb_res = await actuator.rollback(plan, exact_snapshot=initial_snapshot)
    assert dup_rb_res.success
    assert dup_rb_res.is_idempotent_replay


@pytest.mark.asyncio
async def test_cryptographic_audit_ledger_hash_chain():
    """Asserts append-only SHA-256 hash chaining and tamper-evident detection."""
    ledger = CryptographicAuditLedger()

    e1 = ledger.append_entry("plan-1", "PLAN_SYNTHESIZED", "POLICY_ENGINE", {"wf": "order"})
    e2 = ledger.append_entry(
        "plan-1", "ACTUATION_COMMITTED", "AUTONOMOUS_POLICY", {"weights": "shifted"}
    )
    e3 = ledger.append_entry("plan-1", "VERIFICATION_PASSED", "HEALTH_VERIFIER", {"healthy": True})

    assert len(ledger._entries) == 3
    assert e2.previous_hash == e1.entry_hash
    assert e3.previous_hash == e2.entry_hash

    # Valid Chain Check
    is_valid, msg = ledger.verify_chain_integrity()
    assert is_valid
    assert "verified intact" in msg

    # Tampering Simulation: modify payload of entry 2
    ledger._entries[1].payload["malicious"] = "tampered_data"
    is_tampered, tamper_msg = ledger.verify_chain_integrity()
    assert not is_tampered
    assert "Tampered entry detected" in tamper_msg


@pytest.mark.asyncio
async def test_health_verifier_automated_rollback(initial_snapshot: StateSnapshot):
    """Asserts that health degradation automatically triggers emergency rollback."""
    actuator = InMemoryRoutingActuator(initial_state=initial_snapshot)
    ledger = CryptographicAuditLedger()
    verifier = PostActuationHealthVerifier(actuator=actuator, audit_ledger=ledger)

    plan = RemediationActionPlan(
        id="plan-verify-01",
        workflow_definition_id="order_fulfillment",
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.AUTONOMOUS,
        status=ActionPlanStatus.ACTIVE_VERIFYING,
        target_service="customer-db",
        target_parameters={
            "source_path_id": "path_01",
            "target_path_id": "path_02",
            "traffic_shift_pct": 0.20,
        },
        blast_radius_pct=0.20,
        idempotency_key="key-007",
        pre_actuation_state_snapshot=initial_snapshot,
        health_baseline={"p95_latency_ms": 300.0, "error_rate": 0.10},
    )

    # Actuate first
    await actuator.actuate(plan)
    assert (await actuator.get_current_state()).routing_weights["path_01"] == 0.80

    # Simulated degraded post telemetry (latency worsened to 450ms, error rate remains 12%)
    degraded_metrics = {"p95_latency_ms": 450.0, "error_rate": 0.12}
    is_recovered, metrics, msg = await verifier.verify_and_monitor(
        plan, observed_post_metrics=degraded_metrics
    )

    assert not is_recovered
    assert plan.status == ActionPlanStatus.ROLLED_BACK
    assert "Exact pre-actuation state restored verbatim" in msg

    # State restored to baseline
    restored_mesh = await actuator.get_current_state()
    assert restored_mesh.routing_weights["path_01"] == 1.0
    assert restored_mesh.routing_weights["path_02"] == 0.0


@pytest.mark.asyncio
async def test_planner_and_mode_downgrade(
    planner: RemediationActionPlanner, initial_snapshot: StateSnapshot
):
    """Asserts that ambiguous or failing invariants automatically downgrade execution mode."""
    from apps.ml.root_cause import RootCauseReport

    rca = RootCauseReport(
        id="rca-test-01",
        execution_id="exec-01",
        workflow_definition_id="order_fulfillment",
        culprit_service="customer-db",
        incident_category="DATABASE_IOPS_SATURATION",
        confidence=0.98,
        causal_path=["customer-db"],
        supporting_evidence=["IOPS saturation detected"],
        primary_hypothesis=None,  # type: ignore[arg-type]
        alternative_hypotheses=[],
    )

    plan = planner.synthesize_plan_from_diagnostics(
        workflow_definition_id="order_fulfillment",
        rca_report=rca,
        optimization_recommendation=None,
        current_mesh_state=initial_snapshot,
        actuation_history=[
            # Recent actuation violates anti-flapping on customer-db
            {
                "target_service": "customer-db",
                "workflow_definition_id": "order_fulfillment",
                "executed_at": datetime.now(UTC) - timedelta(seconds=30),
            }
        ],
    )

    assert plan.safety_report is not None
    assert not plan.safety_report.is_safe
    assert not plan.safety_report.anti_flapping_passed
    assert plan.execution_mode == ExecutionMode.ADVISORY  # Downgraded from AUTONOMOUS!
