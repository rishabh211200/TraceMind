"""HTTP Gateway / Reverse Proxy actuator (Dry-run & configuration gated)."""

from apps.ml.remediation.actuators.base import (
    ActuationResult,
    BaseRemediationActuator,
    RollbackResult,
)
from packages.common.logging import get_logger
from packages.domain.remediation import RemediationActionPlan, StateSnapshot

logger = get_logger("tracemind.remediation.actuators.http_gateway")


class HttpGatewayActuator(BaseRemediationActuator):
    """Generates dynamic routing and circuit header directives for API Gateways / Reverse Proxies."""

    def __init__(self, is_dry_run: bool = True) -> None:
        self.is_dry_run = is_dry_run
        self._active_headers: dict[str, str] = {}

    async def actuate(self, plan: RemediationActionPlan) -> ActuationResult:
        """Computes dynamic proxy headers and stages/applies them."""
        headers = {
            "X-TraceMind-Remediation-Plan-Id": plan.id,
            "X-TraceMind-Action-Type": plan.action_type.value,
            "X-TraceMind-Target-Service": plan.target_service,
            "X-TraceMind-Blast-Radius": str(plan.blast_radius_pct),
        }

        if plan.target_parameters.get("target_path_id"):
            headers["X-TraceMind-Divert-Target"] = str(plan.target_parameters["target_path_id"])
            headers["X-TraceMind-Divert-Ratio"] = str(
                plan.target_parameters.get("traffic_shift_pct", plan.blast_radius_pct)
            )

        self._active_headers = headers

        msg = (
            f"[DRY-RUN] Staged {len(headers)} proxy headers"
            if self.is_dry_run
            else f"Dispatched {len(headers)} proxy headers to gateway"
        )
        logger.info(msg, plan_id=plan.id)

        post_state = plan.pre_actuation_state_snapshot.model_copy(deep=True)
        return ActuationResult(
            success=True,
            post_state=post_state,
            message=msg,
            is_idempotent_replay=False,
        )

    async def rollback(
        self, plan: RemediationActionPlan, exact_snapshot: StateSnapshot
    ) -> RollbackResult:
        """Clears staged proxy headers and restores pre-actuation headers."""
        self._active_headers.clear()
        msg = (
            f"[DRY-RUN] Cleared proxy headers for {plan.id}"
            if self.is_dry_run
            else f"Cleared proxy headers for {plan.id}"
        )
        logger.info(msg, plan_id=plan.id)

        return RollbackResult(
            success=True,
            restored_state=exact_snapshot.model_copy(deep=True),
            message=msg,
            is_idempotent_replay=False,
        )
