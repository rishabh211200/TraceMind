"""Base abstract interface for remediation actuators."""

from abc import ABC, abstractmethod
from typing import NamedTuple

from packages.domain.remediation import RemediationActionPlan, StateSnapshot


class ActuationResult(NamedTuple):
    """Result of an operational mitigation actuation."""

    success: bool
    post_state: StateSnapshot
    message: str
    is_idempotent_replay: bool = False


class RollbackResult(NamedTuple):
    """Result of an exact-state rollback operation."""

    success: bool
    restored_state: StateSnapshot
    message: str
    is_idempotent_replay: bool = False


class BaseRemediationActuator(ABC):
    """Abstract actuator interface for applying and rolling back operational mitigations."""

    @abstractmethod
    async def actuate(self, plan: RemediationActionPlan) -> ActuationResult:
        """Actuate a remediation action plan."""
        pass

    @abstractmethod
    async def rollback(
        self, plan: RemediationActionPlan, exact_snapshot: StateSnapshot
    ) -> RollbackResult:
        """Roll back an actuated plan by verbatim restoring the exact pre-actuation state snapshot."""
        pass
