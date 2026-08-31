"""Remediation Policy Engine for matching declarative mitigation rules and resolving execution modes."""

from typing import Any

from apps.ml.remediation.safety_guards import SafetyInvariantEvaluator
from packages.common.logging import get_logger
from packages.domain.remediation import (
    ActionType,
    ExecutionMode,
    RemediationActionPlan,
    RemediationPolicy,
    SafetyCheckReport,
)

logger = get_logger("tracemind.remediation.policy")


class RemediationPolicyEngine:
    """Evaluates declarative policies and safety invariants to govern remediation execution."""

    def __init__(
        self,
        safety_evaluator: SafetyInvariantEvaluator | None = None,
    ) -> None:
        self.safety_evaluator = safety_evaluator or SafetyInvariantEvaluator()
        self._policies: dict[str, RemediationPolicy] = {}
        self._seed_default_policies()

    def _seed_default_policies(self) -> None:
        """Seed default canonical self-healing policies across known failure signatures."""
        defaults = [
            RemediationPolicy(
                id="pol-db-saturation",
                name="Database IOPS Saturation Autonomous Diversion",
                workflow_definition_id="*",
                incident_category="DATABASE_IOPS_SATURATION",
                action_type=ActionType.TRAFFIC_DIVERT,
                execution_mode=ExecutionMode.AUTONOMOUS,
                max_blast_radius=0.25,
                cooldown_seconds=300,
                verification_timeout_seconds=45,
            ),
            RemediationPolicy(
                id="pol-service-crash",
                name="Service Crash Fast Circuit Trip",
                workflow_definition_id="*",
                incident_category="SERVICE_CRASH",
                action_type=ActionType.CIRCUIT_BREAK,
                execution_mode=ExecutionMode.AUTONOMOUS,
                max_blast_radius=0.30,
                cooldown_seconds=300,
                verification_timeout_seconds=30,
            ),
            RemediationPolicy(
                id="pol-retry-storm",
                name="Cascading Retry Storm Adaptive Exponential Backoff",
                workflow_definition_id="*",
                incident_category="CASCADING_RETRY_STORM",
                action_type=ActionType.RETRY_BACKOFF_ADAPT,
                execution_mode=ExecutionMode.AUTONOMOUS,
                max_blast_radius=0.30,
                cooldown_seconds=180,
                verification_timeout_seconds=30,
            ),
            RemediationPolicy(
                id="pol-payment-degradation",
                name="Payment Gateway Degradation Supervised Diversion",
                workflow_definition_id="*",
                incident_category="PAYMENT_DEGRADATION",
                action_type=ActionType.TRAFFIC_DIVERT,
                execution_mode=ExecutionMode.SUPERVISED,
                max_blast_radius=0.20,
                cooldown_seconds=300,
                verification_timeout_seconds=60,
            ),
            RemediationPolicy(
                id="pol-flash-traffic",
                name="Flash Traffic Surge Concurrency Throttling",
                workflow_definition_id="*",
                incident_category="FLASH_TRAFFIC_OVERLOAD",
                action_type=ActionType.CONCURRENCY_THROTTLE,
                execution_mode=ExecutionMode.SUPERVISED,
                max_blast_radius=0.20,
                cooldown_seconds=300,
                verification_timeout_seconds=45,
            ),
            RemediationPolicy(
                id="pol-network-latency",
                name="Transit Latency Alternative Route Diversion",
                workflow_definition_id="*",
                incident_category="NETWORK_TRANSIT_DELAY",
                action_type=ActionType.TRAFFIC_DIVERT,
                execution_mode=ExecutionMode.SUPERVISED,
                max_blast_radius=0.25,
                cooldown_seconds=300,
                verification_timeout_seconds=45,
            ),
            RemediationPolicy(
                id="pol-dependency-timeout",
                name="Dependency Timeout Circuit Break",
                workflow_definition_id="*",
                incident_category="DEPENDENCY_TIMEOUT",
                action_type=ActionType.CIRCUIT_BREAK,
                execution_mode=ExecutionMode.SUPERVISED,
                max_blast_radius=0.20,
                cooldown_seconds=300,
                verification_timeout_seconds=30,
            ),
        ]
        for pol in defaults:
            self._policies[pol.id] = pol

    def register_policy(self, policy: RemediationPolicy) -> None:
        """Register or update a declarative remediation policy."""
        self._policies[policy.id] = policy
        logger.info("Registered remediation policy", policy_id=policy.id, name=policy.name)

    def get_policy(self, policy_id: str) -> RemediationPolicy | None:
        """Retrieve policy by identifier."""
        return self._policies.get(policy_id)

    def list_policies(self, active_only: bool = True) -> list[RemediationPolicy]:
        """List all registered remediation policies."""
        if active_only:
            return [p for p in self._policies.values() if p.is_active]
        return list(self._policies.values())

    def delete_policy(self, policy_id: str) -> bool:
        """Deactivate or remove a remediation policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def match_policy(
        self,
        workflow_definition_id: str,
        incident_category: str | None,
        preferred_action: ActionType | None = None,
    ) -> RemediationPolicy | None:
        """Finds the highest-priority matching active policy for a workflow and incident signature."""
        category = incident_category or "*"

        for pol in self._policies.values():
            if not pol.is_active:
                continue

            # Check workflow ID match
            wf_match = (
                pol.workflow_definition_id == "*"
                or pol.workflow_definition_id == workflow_definition_id
            )
            if not wf_match:
                continue

            # Check incident category match
            cat_match = pol.incident_category == "*" or pol.incident_category == category
            if not cat_match:
                continue

            # Check action match if requested
            if preferred_action and pol.action_type != preferred_action:
                continue

            return pol

        return None

    def evaluate_plan_policy(
        self,
        plan: RemediationActionPlan,
        actuation_history: list[dict[str, Any]] | None = None,
        root_cause_culprit: str | None = None,
        target_path_services: list[str] | None = None,
        target_path_spare_capacity: float = 0.50,
        diagnostic_confidence: float = 0.98,
    ) -> tuple[ExecutionMode, SafetyCheckReport]:
        """Evaluates policy and runs safety invariants to resolve final execution mode."""
        policy = self.get_policy(plan.policy_id) if plan.policy_id else None

        policy_max_blast = policy.max_blast_radius if policy else None
        policy_cooldown = policy.cooldown_seconds if policy else None

        safety_report = self.safety_evaluator.evaluate_all_invariants(
            plan=plan,
            actuation_history=actuation_history,
            root_cause_culprit=root_cause_culprit,
            target_path_services=target_path_services,
            target_path_spare_capacity=target_path_spare_capacity,
            policy_max_blast=policy_max_blast,
            policy_cooldown_seconds=policy_cooldown,
        )

        # Strict execution mode resolution:
        # AUTONOMOUS requires:
        # 1. Policy exists and explicitly configures AUTONOMOUS
        # 2. All safety invariants pass (safety_report.is_safe is True)
        # 3. Diagnostic / RCA confidence >= 0.95
        if not safety_report.is_safe:
            resolved_mode = ExecutionMode.ADVISORY
        elif (
            policy
            and policy.execution_mode == ExecutionMode.AUTONOMOUS
            and diagnostic_confidence >= 0.95
        ):
            resolved_mode = ExecutionMode.AUTONOMOUS
        else:
            resolved_mode = ExecutionMode.SUPERVISED

        return resolved_mode, safety_report
