"""Deterministic safety invariant evaluation engine for Autonomous Remediation."""

from datetime import UTC, datetime, timedelta
from typing import Any

from packages.common.logging import get_logger
from packages.domain.remediation import (
    ActionType,
    ExecutionMode,
    RemediationActionPlan,
    SafetyCheckReport,
)

logger = get_logger("tracemind.remediation.safety")

MAX_GLOBAL_BLAST_RADIUS = 0.30
MAX_THROTTLE_PERCENTAGE = 0.25
MAX_HOURLY_ACTUATIONS_PER_WORKFLOW = 3
MIN_CAPACITY_HEADROOM_RATIO = 0.40


class SafetyInvariantEvaluator:
    """Evaluates strict deterministic safety invariants before any remediation plan is executed."""

    def __init__(
        self,
        max_blast_radius: float = MAX_GLOBAL_BLAST_RADIUS,
        default_cooldown_seconds: int = 300,
    ) -> None:
        self.max_blast_radius = max_blast_radius
        self.default_cooldown_seconds = default_cooldown_seconds

    def validate_blast_radius(
        self, plan: RemediationActionPlan, policy_max_blast: float | None = None
    ) -> tuple[bool, str]:
        """Asserts that traffic shift or throttle volume does not exceed strict blast radius limits."""
        effective_limit = min(
            policy_max_blast if policy_max_blast is not None else self.max_blast_radius,
            self.max_blast_radius,
        )

        if plan.action_type == ActionType.CONCURRENCY_THROTTLE:
            throttle_pct = plan.target_parameters.get("throttle_percentage", 0.0)
            if throttle_pct > MAX_THROTTLE_PERCENTAGE:
                return (
                    False,
                    f"Throttle percentage {throttle_pct:.1%} exceeds maximum safety limit {MAX_THROTTLE_PERCENTAGE:.1%}",
                )

        if plan.blast_radius_pct > effective_limit:
            return (
                False,
                f"Plan blast radius {plan.blast_radius_pct:.1%} exceeds maximum permitted {effective_limit:.1%}",
            )

        return (
            True,
            f"Blast radius {plan.blast_radius_pct:.1%} within safety limit {effective_limit:.1%}",
        )

    def validate_anti_flapping(
        self,
        plan: RemediationActionPlan,
        actuation_history: list[dict[str, Any]],
        cooldown_seconds: int | None = None,
    ) -> tuple[bool, str]:
        """Prevents rapid oscillatory toggling of mitigations on the same service or workflow."""
        effective_cooldown = cooldown_seconds or self.default_cooldown_seconds
        now = datetime.now(UTC)
        cutoff_time = now - timedelta(seconds=effective_cooldown)
        hourly_cutoff = now - timedelta(hours=1)

        recent_service_actuations = [
            h
            for h in actuation_history
            if h.get("target_service") == plan.target_service
            and isinstance(h.get("executed_at"), datetime)
            and h["executed_at"] >= cutoff_time
        ]
        if recent_service_actuations:
            return (
                False,
                f"Target service '{plan.target_service}' was modified {len(recent_service_actuations)} time(s) within cooldown period ({effective_cooldown}s)",
            )

        workflow_hourly_actuations = [
            h
            for h in actuation_history
            if h.get("workflow_definition_id") == plan.workflow_definition_id
            and isinstance(h.get("executed_at"), datetime)
            and h["executed_at"] >= hourly_cutoff
        ]

        if len(workflow_hourly_actuations) >= MAX_HOURLY_ACTUATIONS_PER_WORKFLOW:
            return (
                False,
                f"Workflow '{plan.workflow_definition_id}' exceeded max hourly actuation cap ({MAX_HOURLY_ACTUATIONS_PER_WORKFLOW}/hr)",
            )

        return True, "Anti-flapping and cooldown constraints satisfied"

    def validate_dependency_acyclicity(
        self,
        plan: RemediationActionPlan,
        root_cause_culprit: str | None = None,
        target_path_services: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Asserts that alternative path routing does not route traffic through the root cause culprit or create cycles."""
        if plan.action_type == ActionType.TRAFFIC_DIVERT and target_path_services:
            if root_cause_culprit and root_cause_culprit in target_path_services:
                return (
                    False,
                    f"Alternative diversion path contains active root culprit '{root_cause_culprit}', which would worsen the cascade",
                )

            # Circular routing check: ensure no duplicate services in alternative chain
            if len(target_path_services) != len(set(target_path_services)):
                return (
                    False,
                    "Alternative diversion path contains duplicate service hops (potential routing cycle)",
                )

        return True, "Dependency acyclicity and culprit isolation verified"

    def validate_capacity_headroom(
        self,
        plan: RemediationActionPlan,
        target_path_spare_capacity_ratio: float = 0.50,
    ) -> tuple[bool, str]:
        """Asserts that the backup / diversion path has sufficient spare capacity to absorb traffic."""
        if plan.action_type == ActionType.TRAFFIC_DIVERT:
            divert_ratio = plan.target_parameters.get("traffic_shift_pct", plan.blast_radius_pct)
            if target_path_spare_capacity_ratio < MIN_CAPACITY_HEADROOM_RATIO:
                return (
                    False,
                    f"Target diversion path spare capacity ({target_path_spare_capacity_ratio:.1%}) is below safety threshold ({MIN_CAPACITY_HEADROOM_RATIO:.1%})",
                )
            if divert_ratio > target_path_spare_capacity_ratio:
                return (
                    False,
                    f"Requested traffic shift ({divert_ratio:.1%}) exceeds target path spare capacity ({target_path_spare_capacity_ratio:.1%})",
                )

        return True, "Target path capacity headroom verified"

    def evaluate_all_invariants(
        self,
        plan: RemediationActionPlan,
        actuation_history: list[dict[str, Any]] | None = None,
        root_cause_culprit: str | None = None,
        target_path_services: list[str] | None = None,
        target_path_spare_capacity: float = 0.50,
        policy_max_blast: float | None = None,
        policy_cooldown_seconds: int | None = None,
    ) -> SafetyCheckReport:
        """Executes full invariant suite with fail-safe error handling and automatic mode downgrade."""
        details: dict[str, str] = {}
        rejections: list[str] = []

        history = actuation_history or []

        try:
            # 1. Blast Radius
            blast_ok, blast_msg = self.validate_blast_radius(plan, policy_max_blast)
            details["blast_radius"] = blast_msg
            if not blast_ok:
                rejections.append(blast_msg)

            # 2. Anti-Flapping
            flapping_ok, flapping_msg = self.validate_anti_flapping(
                plan, history, policy_cooldown_seconds
            )
            details["anti_flapping"] = flapping_msg
            if not flapping_ok:
                rejections.append(flapping_msg)

            # 3. Acyclicity & Culprit Isolation
            acyclic_ok, acyclic_msg = self.validate_dependency_acyclicity(
                plan, root_cause_culprit, target_path_services
            )
            details["acyclicity"] = acyclic_msg
            if not acyclic_ok:
                rejections.append(acyclic_msg)

            # 4. Capacity Headroom
            capacity_ok, capacity_msg = self.validate_capacity_headroom(
                plan, target_path_spare_capacity
            )
            details["capacity_headroom"] = capacity_msg
            if not capacity_ok:
                rejections.append(capacity_msg)

            all_passed = blast_ok and flapping_ok and acyclic_ok and capacity_ok

            # Strict mode resolution: fail toward SUPERVISED/ADVISORY
            if all_passed:
                recommended_mode = (
                    ExecutionMode.AUTONOMOUS
                    if plan.execution_mode == ExecutionMode.AUTONOMOUS
                    else ExecutionMode.SUPERVISED
                )
            else:
                recommended_mode = ExecutionMode.ADVISORY

            return SafetyCheckReport(
                is_safe=all_passed,
                blast_radius_passed=blast_ok,
                anti_flapping_passed=flapping_ok,
                acyclicity_passed=acyclic_ok,
                capacity_headroom_passed=capacity_ok,
                checks_details=details,
                rejection_reasons=rejections,
                recommended_mode=recommended_mode,
            )

        except Exception as ex:
            logger.error("Safety invariant evaluation encountered exception", error=str(ex))
            return SafetyCheckReport(
                is_safe=False,
                blast_radius_passed=False,
                anti_flapping_passed=False,
                acyclicity_passed=False,
                capacity_headroom_passed=False,
                checks_details={"error": f"Evaluation exception: {ex}"},
                rejection_reasons=[f"Fail-safe exception: {ex}"],
                recommended_mode=ExecutionMode.ADVISORY,
            )
