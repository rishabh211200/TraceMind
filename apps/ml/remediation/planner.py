import hashlib
import uuid
from typing import Any

from apps.ml.optimizer.models import OptimizationRecommendation
from apps.ml.remediation.policy_engine import RemediationPolicyEngine
from apps.ml.root_cause import RootCauseReport
from packages.common.logging import get_logger
from packages.domain.remediation import (
    ActionPlanStatus,
    ActionType,
    ExecutionMode,
    RemediationActionPlan,
    StateSnapshot,
)

logger = get_logger("tracemind.remediation.planner")


class RemediationActionPlanner:
    """Synthesizes deterministic, safety-evaluated remediation action plans from platform diagnostics."""

    def __init__(self, policy_engine: RemediationPolicyEngine | None = None) -> None:
        self.policy_engine = policy_engine or RemediationPolicyEngine()

    def generate_idempotency_key(
        self,
        workflow_id: str,
        incident_id: str | None,
        target_service: str,
        action_type: ActionType,
        target_path_id: str | None = None,
    ) -> str:
        """Generates a deterministic SHA-256 idempotency key to prevent duplicate mutations."""
        seed_str = f"{workflow_id}:{incident_id or 'none'}:{target_service}:{action_type.value}:{target_path_id or 'none'}"
        return hashlib.sha256(seed_str.encode("utf-8")).hexdigest()

    def synthesize_plan_from_diagnostics(
        self,
        workflow_definition_id: str,
        rca_report: RootCauseReport | None = None,
        optimization_recommendation: OptimizationRecommendation | None = None,
        current_mesh_state: StateSnapshot | None = None,
        health_baseline: dict[str, float] | None = None,
        actuation_history: list[dict[str, Any]] | None = None,
    ) -> RemediationActionPlan:
        """Synthesizes a complete RemediationActionPlan from M8 RCA and M9 Pareto recommendations."""
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        incident_cat = rca_report.incident_category if rca_report else None
        incident_id = rca_report.execution_id if rca_report else None
        root_culprit = rca_report.culprit_service if rca_report else "unknown-service"
        confidence = rca_report.confidence if rca_report else 0.95

        # 1. Determine target action type based on fault signature
        action_type = ActionType.TRAFFIC_DIVERT
        target_params: dict[str, Any] = {}
        blast_radius = 0.20
        target_path_services: list[str] | None = None

        if incident_cat == "DATABASE_IOPS_SATURATION":
            action_type = ActionType.TRAFFIC_DIVERT
            blast_radius = 0.25
            target_params = {
                "source_path_id": "path_db_heavy",
                "target_path_id": "path_cache_accelerated",
                "traffic_shift_pct": blast_radius,
                "strategy": "divert_reads_to_cache",
            }
            target_path_services = ["customer-service", "customer-cache"]

        elif incident_cat == "SERVICE_CRASH":
            action_type = ActionType.CIRCUIT_BREAK
            blast_radius = 0.30
            target_params = {
                "service": root_culprit,
                "circuit_action": "TRIP_OPEN",
                "fallback_mode": "FAST_FAIL_GRACEFUL",
            }

        elif incident_cat == "CASCADING_RETRY_STORM":
            action_type = ActionType.RETRY_BACKOFF_ADAPT
            blast_radius = 0.25
            target_params = {
                "service": root_culprit,
                "multiplier": 3.0,
                "jitter_pct": 0.20,
            }

        elif incident_cat == "FLASH_TRAFFIC_OVERLOAD":
            action_type = ActionType.CONCURRENCY_THROTTLE
            blast_radius = 0.20
            target_params = {
                "service": root_culprit,
                "throttle_percentage": 0.20,
                "concurrency_limit": 50,
            }

        elif incident_cat == "PAYMENT_DEGRADATION":
            action_type = ActionType.TRAFFIC_DIVERT
            blast_radius = 0.20
            target_params = {
                "source_path_id": "path_primary_gateway",
                "target_path_id": "path_backup_gateway",
                "traffic_shift_pct": blast_radius,
            }
            target_path_services = ["payment-service", "backup-gateway"]

        # Incorporate M9 Pareto recommendation if provided
        expected_savings: dict[str, float] = {}
        if optimization_recommendation:
            sav = optimization_recommendation.expected_savings
            expected_savings = {
                "latency_reduction_pct": sav.latency_reduction_pct,
                "cost_reduction_pct": sav.cost_reduction_pct,
                "reliability_gain_pct": sav.reliability_gain_pct,
            }
            if optimization_recommendation.recommended_path:
                target_params["target_path_id"] = (
                    optimization_recommendation.recommended_path.path_id
                )
                target_path_services = [
                    s.service for s in optimization_recommendation.recommended_path.steps
                ]

        # 2. Capture Pre-Actuation State Snapshot verbatim
        state_snap = current_mesh_state or StateSnapshot(
            routing_weights={"path_01": 1.0, "path_02": 0.0},
            circuit_states={root_culprit: "CLOSED"},
            concurrency_limits={root_culprit: 100},
            retry_multipliers={root_culprit: 1.0},
        )

        # 3. Match Policy
        matched_policy = self.policy_engine.match_policy(
            workflow_definition_id=workflow_definition_id,
            incident_category=incident_cat,
            preferred_action=action_type,
        )

        idempotency_key = self.generate_idempotency_key(
            workflow_id=workflow_definition_id,
            incident_id=incident_id,
            target_service=root_culprit,
            action_type=action_type,
            target_path_id=target_params.get("target_path_id"),
        )

        initial_plan = RemediationActionPlan(
            id=plan_id,
            policy_id=matched_policy.id if matched_policy else None,
            workflow_definition_id=workflow_definition_id,
            incident_id=incident_id,
            trigger_rca_id=rca_report.execution_id if rca_report else None,
            action_type=action_type,
            execution_mode=matched_policy.execution_mode
            if matched_policy
            else ExecutionMode.SUPERVISED,
            status=ActionPlanStatus.STAGED,
            target_service=root_culprit,
            target_parameters=target_params,
            blast_radius_pct=blast_radius,
            idempotency_key=idempotency_key,
            expected_savings=expected_savings,
            pre_actuation_state_snapshot=state_snap,
            health_baseline=health_baseline or {"p95_latency_ms": 320.0, "error_rate": 0.15},
        )

        # 4. Evaluate Safety Invariants & Resolve Final Execution Mode
        resolved_mode, safety_report = self.policy_engine.evaluate_plan_policy(
            plan=initial_plan,
            actuation_history=actuation_history,
            root_cause_culprit=root_culprit,
            target_path_services=target_path_services,
            diagnostic_confidence=confidence,
        )

        initial_plan.execution_mode = resolved_mode
        initial_plan.safety_report = safety_report

        logger.info(
            "Synthesized remediation action plan",
            plan_id=initial_plan.id,
            action_type=initial_plan.action_type.value,
            resolved_mode=initial_plan.execution_mode.value,
            is_safe=safety_report.is_safe,
        )

        return initial_plan
