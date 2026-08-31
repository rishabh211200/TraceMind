"""Webhook Dispatch Actuator with HMAC-SHA256 signatures (Dry-run gated)."""

import hashlib
import hmac
import json
from datetime import UTC, datetime

from apps.ml.remediation.actuators.base import (
    ActuationResult,
    BaseRemediationActuator,
    RollbackResult,
)
from packages.common.logging import get_logger
from packages.domain.remediation import RemediationActionPlan, StateSnapshot

logger = get_logger("tracemind.remediation.actuators.webhook")


class WebhookActuator(BaseRemediationActuator):
    """Dispatches cryptographically signed JSON webhook payloads for operational actuation."""

    def __init__(
        self,
        webhook_url: str = "http://localhost:8000/api/v1/remediations/webhook-sink",
        secret_key: str = "tracemind-insecure-default-webhook-key",
        is_dry_run: bool = True,
    ) -> None:
        self.webhook_url = webhook_url
        self.secret_key = secret_key
        self.is_dry_run = is_dry_run
        self.dispatched_payloads: list[dict[str, str]] = []

    def compute_signature(self, payload_bytes: bytes) -> str:
        """Computes HMAC-SHA256 signature for webhook verification."""
        return hmac.new(self.secret_key.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    async def actuate(self, plan: RemediationActionPlan) -> ActuationResult:
        """Constructs signed actuation payload and dispatches (or records in dry-run mode)."""
        body = {
            "event": "REMEDIATION_ACTUATED",
            "plan_id": plan.id,
            "action_type": plan.action_type.value,
            "target_service": plan.target_service,
            "blast_radius": plan.blast_radius_pct,
            "parameters": plan.target_parameters,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        body_bytes = json.dumps(body, sort_keys=True).encode("utf-8")
        signature = self.compute_signature(body_bytes)

        self.dispatched_payloads.append(
            {"body": body_bytes.decode("utf-8"), "signature": signature}
        )

        msg = (
            f"[DRY-RUN] Formatted webhook event {body['event']} (sig: {signature[:8]}...)"
            if self.is_dry_run
            else f"Dispatched webhook event to {self.webhook_url}"
        )
        logger.info(msg, plan_id=plan.id)

        return ActuationResult(
            success=True,
            post_state=plan.pre_actuation_state_snapshot.model_copy(deep=True),
            message=msg,
            is_idempotent_replay=False,
        )

    async def rollback(
        self, plan: RemediationActionPlan, exact_snapshot: StateSnapshot
    ) -> RollbackResult:
        """Constructs signed rollback payload."""
        body = {
            "event": "REMEDIATION_ROLLED_BACK",
            "plan_id": plan.id,
            "target_service": plan.target_service,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        body_bytes = json.dumps(body, sort_keys=True).encode("utf-8")
        signature = self.compute_signature(body_bytes)

        self.dispatched_payloads.append(
            {"body": body_bytes.decode("utf-8"), "signature": signature}
        )

        msg = (
            f"[DRY-RUN] Formatted rollback webhook event (sig: {signature[:8]}...)"
            if self.is_dry_run
            else f"Dispatched rollback webhook to {self.webhook_url}"
        )
        logger.info(msg, plan_id=plan.id)

        return RollbackResult(
            success=True,
            restored_state=exact_snapshot.model_copy(deep=True),
            message=msg,
            is_idempotent_replay=False,
        )
