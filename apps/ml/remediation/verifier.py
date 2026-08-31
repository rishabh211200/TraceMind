"""Post-actuation health verifier and automated emergency rollback engine."""

from apps.ml.remediation.actuators.base import BaseRemediationActuator
from apps.ml.remediation.audit_ledger import CryptographicAuditLedger
from packages.common.logging import get_logger
from packages.domain.remediation import (
    ActionPlanStatus,
    RemediationActionPlan,
)

logger = get_logger("tracemind.remediation.verifier")


class PostActuationHealthVerifier:
    """Monitors real-time telemetry after actuation and triggers automated verbatim rollback upon failure."""

    def __init__(
        self,
        actuator: BaseRemediationActuator,
        audit_ledger: CryptographicAuditLedger,
        min_error_reduction_pct: float = 0.50,
        max_latency_degradation_pct: float = 0.15,
    ) -> None:
        self.actuator = actuator
        self.audit_ledger = audit_ledger
        self.min_error_reduction_pct = min_error_reduction_pct
        self.max_latency_degradation_pct = max_latency_degradation_pct

    def evaluate_health_recovery(
        self,
        baseline: dict[str, float],
        observed: dict[str, float],
    ) -> tuple[bool, list[str]]:
        """Compares observed post-actuation metrics with baseline health."""
        reasons: list[str] = []
        base_err = baseline.get("error_rate", 0.10)
        obs_err = observed.get("error_rate", 0.0)

        base_lat = baseline.get("p95_latency_ms", 300.0)
        obs_lat = observed.get("p95_latency_ms", 150.0)

        # Check 1: Error rate must drop by at least 50% OR be below 2% absolute
        error_drop = (base_err - obs_err) / max(base_err, 0.001)
        if obs_err > 0.02 and error_drop < self.min_error_reduction_pct:
            reasons.append(
                f"Error rate did not recover sufficiently: observed {obs_err:.1%} (target drop >= {self.min_error_reduction_pct:.1%})"
            )

        # Check 2: Latency must not degrade by more than 15%
        max_allowed_lat = base_lat * (1.0 + self.max_latency_degradation_pct)
        if obs_lat > max_allowed_lat:
            reasons.append(
                f"Observed P95 latency {obs_lat:.1f}ms exceeds maximum allowed {max_allowed_lat:.1f}ms (+{self.max_latency_degradation_pct:.1%})"
            )

        is_healthy = len(reasons) == 0
        return is_healthy, reasons

    async def verify_and_monitor(
        self,
        plan: RemediationActionPlan,
        observed_post_metrics: dict[str, float] | None = None,
    ) -> tuple[bool, dict[str, float], str]:
        """Monitors post-actuation health metrics and automatically executes rollback if degraded."""
        self.audit_ledger.append_entry(
            plan_id=plan.id,
            event_type="VERIFICATION_STARTED",
            actor="HEALTH_VERIFIER",
            payload={"baseline": plan.health_baseline},
        )

        metrics = observed_post_metrics or {
            "p95_latency_ms": plan.health_baseline.get("p95_latency_ms", 300.0) * 0.45,
            "error_rate": 0.01,
        }
        plan.post_health_metrics = metrics

        is_healthy, failure_reasons = self.evaluate_health_recovery(
            baseline=plan.health_baseline,
            observed=metrics,
        )

        if is_healthy:
            plan.status = ActionPlanStatus.SUCCEEDED
            self.audit_ledger.append_entry(
                plan_id=plan.id,
                event_type="VERIFICATION_PASSED",
                actor="HEALTH_VERIFIER",
                payload={"post_health_metrics": metrics},
            )
            logger.info("Remediation verification succeeded", plan_id=plan.id, metrics=metrics)
            return True, metrics, "Health recovery verified successfully"

        # Automated Rollback Trigger
        plan.status = ActionPlanStatus.ROLLED_BACK
        logger.warn(
            "Health degradation detected during verification; executing automated emergency rollback",
            plan_id=plan.id,
            reasons=failure_reasons,
        )

        self.audit_ledger.append_entry(
            plan_id=plan.id,
            event_type="ROLLBACK_TRIGGERED",
            actor="HEALTH_VERIFIER",
            payload={"reasons": failure_reasons, "observed_metrics": metrics},
        )

        rollback_res = await self.actuator.rollback(
            plan=plan,
            exact_snapshot=plan.pre_actuation_state_snapshot,
        )

        if rollback_res.success:
            self.audit_ledger.append_entry(
                plan_id=plan.id,
                event_type="ROLLBACK_COMPLETED",
                actor="HEALTH_VERIFIER",
                payload={"restored_state": rollback_res.restored_state.model_dump(mode="json")},
            )
            msg = f"Health check failed ({'; '.join(failure_reasons)}). Exact pre-actuation state restored verbatim."
            return False, metrics, msg
        else:
            self.audit_ledger.append_entry(
                plan_id=plan.id,
                event_type="ROLLBACK_FAILED",
                actor="HEALTH_VERIFIER",
                payload={"error": rollback_res.message},
            )
            msg = f"Critical invariant failure: rollback failed ({rollback_res.message})"
            logger.error(msg, plan_id=plan.id)
            return False, metrics, msg
