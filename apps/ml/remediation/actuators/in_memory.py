"""In-memory concurrency-safe routing and circuit breaker actuator (Default Executable)."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime

from apps.ml.remediation.actuators.base import (
    ActuationResult,
    BaseRemediationActuator,
    RollbackResult,
)
from packages.common.logging import get_logger
from packages.domain.remediation import (
    ActionType,
    RemediationActionPlan,
    StateSnapshot,
)

logger = get_logger("tracemind.remediation.actuators.in_memory")


class InMemoryRoutingActuator(BaseRemediationActuator):
    """Concurrency-safe in-memory actuator managing runtime routing tables and circuit states."""

    def __init__(self, initial_state: StateSnapshot | None = None) -> None:
        self._lock = asyncio.Lock()
        self._current_state = initial_state or StateSnapshot(
            routing_weights={"path_01": 1.0, "path_02": 0.0},
            circuit_states={"default": "CLOSED"},
            concurrency_limits={"default": 100},
            retry_multipliers={"default": 1.0},
        )
        self._executed_plans: dict[str, StateSnapshot] = {}
        self._rolled_back_plans: dict[str, StateSnapshot] = {}

    async def get_current_state(self) -> StateSnapshot:
        """Returns an atomic deep-copy of the active mesh state."""
        async with self._lock:
            return deepcopy(self._current_state)

    async def actuate(self, plan: RemediationActionPlan) -> ActuationResult:
        """Atomically actuates a remediation action plan with concurrency locking and idempotency protection."""
        async with self._lock:
            # 1. Idempotency Check: if this plan was already executed, return cached post-state
            if plan.id in self._executed_plans:
                logger.info(
                    "Idempotent actuation request detected; returning cached post-state",
                    plan_id=plan.id,
                )
                return ActuationResult(
                    success=True,
                    post_state=deepcopy(self._executed_plans[plan.id]),
                    message="Idempotent replay: plan was already actuated",
                    is_idempotent_replay=True,
                )

            # 2. Capture working state clone to prevent partial mutations on error
            working_state = deepcopy(self._current_state)
            params = plan.target_parameters

            try:
                if plan.action_type == ActionType.TRAFFIC_DIVERT:
                    src = params.get("source_path_id", "path_01")
                    tgt = params.get("target_path_id", "path_02")
                    shift = float(params.get("traffic_shift_pct", plan.blast_radius_pct))

                    current_src_weight = working_state.routing_weights.get(src, 1.0)
                    current_tgt_weight = working_state.routing_weights.get(tgt, 0.0)

                    actual_shift = min(current_src_weight, shift)
                    working_state.routing_weights[src] = max(
                        0.0, round(current_src_weight - actual_shift, 4)
                    )
                    working_state.routing_weights[tgt] = round(current_tgt_weight + actual_shift, 4)

                elif plan.action_type == ActionType.CIRCUIT_BREAK:
                    svc = plan.target_service
                    working_state.circuit_states[svc] = "OPEN"

                elif plan.action_type == ActionType.CONCURRENCY_THROTTLE:
                    svc = plan.target_service
                    limit = int(params.get("concurrency_limit", 50))
                    working_state.concurrency_limits[svc] = limit

                elif plan.action_type == ActionType.RETRY_BACKOFF_ADAPT:
                    svc = plan.target_service
                    multiplier = float(params.get("multiplier", 3.0))
                    working_state.retry_multipliers[svc] = multiplier

                elif plan.action_type == ActionType.CACHE_FALLBACK_ACTUATE:
                    svc = plan.target_service
                    working_state.circuit_states[f"{svc}:cache_mode"] = "CACHE_ONLY"

                working_state.captured_at = datetime.now(UTC)

                # 3. Commit atomic state transition
                self._current_state = working_state
                self._executed_plans[plan.id] = deepcopy(working_state)

                logger.info(
                    "Actuation committed successfully",
                    plan_id=plan.id,
                    action_type=plan.action_type.value,
                    target_service=plan.target_service,
                )

                return ActuationResult(
                    success=True,
                    post_state=deepcopy(self._current_state),
                    message=f"Actuated {plan.action_type.value} on {plan.target_service}",
                    is_idempotent_replay=False,
                )

            except Exception as ex:
                logger.error(
                    "Actuation failed; working state discarded", error=str(ex), plan_id=plan.id
                )
                return ActuationResult(
                    success=False,
                    post_state=deepcopy(self._current_state),
                    message=f"Actuation failure: {ex}",
                    is_idempotent_replay=False,
                )

    async def rollback(
        self, plan: RemediationActionPlan, exact_snapshot: StateSnapshot
    ) -> RollbackResult:
        """Atomically restores the verbatim pre-actuation state snapshot."""
        async with self._lock:
            # 1. Idempotency Check: if rollback for this plan was already executed
            if plan.id in self._rolled_back_plans:
                logger.info(
                    "Idempotent rollback request detected; returning cached restored state",
                    plan_id=plan.id,
                )
                return RollbackResult(
                    success=True,
                    restored_state=deepcopy(self._rolled_back_plans[plan.id]),
                    message="Idempotent replay: plan rollback was already executed",
                    is_idempotent_replay=True,
                )

            try:
                # 2. Verbatim Exact-State Restoration
                restored = deepcopy(exact_snapshot)
                restored.captured_at = datetime.now(UTC)

                self._current_state = restored
                self._rolled_back_plans[plan.id] = deepcopy(restored)

                logger.info(
                    "Verbatim exact-state rollback restored successfully",
                    plan_id=plan.id,
                    target_service=plan.target_service,
                )

                return RollbackResult(
                    success=True,
                    restored_state=deepcopy(self._current_state),
                    message=f"Verbatim pre-actuation state snapshot restored for {plan.id}",
                    is_idempotent_replay=False,
                )

            except Exception as ex:
                logger.error("Rollback failed critical invariant", error=str(ex), plan_id=plan.id)
                return RollbackResult(
                    success=False,
                    restored_state=deepcopy(self._current_state),
                    message=f"Rollback failure: {ex}",
                    is_idempotent_replay=False,
                )
