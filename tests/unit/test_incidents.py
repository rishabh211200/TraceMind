"""Unit tests for chaos scenarios and ground-truth incident preservation."""

from datetime import UTC, datetime

import pytest

from apps.simulator.config import SimulationConfig
from apps.simulator.distributions import DeterministicSampler
from apps.simulator.incidents import IncidentEngine
from apps.simulator.workflow_engine import TraceSimulator
from packages.domain.incident import IncidentScenario
from packages.domain.workflow import ExecutionStatus


@pytest.mark.parametrize(
    "scenario",
    [
        IncidentScenario.DATABASE_LATENCY,
        IncidentScenario.PAYMENT_LATENCY_DEGRADATION,
        IncidentScenario.TRAFFIC_SPIKE,
        IncidentScenario.SERVICE_FAILURE,
        IncidentScenario.NETWORK_LATENCY,
        IncidentScenario.RETRY_STORM,
        IncidentScenario.CASCADING_FAILURE,
    ],
)
def test_explicit_incident_injection(scenario: IncidentScenario):
    """Verify that every supported chaos scenario schedules ground truth and affects executions."""
    cfg = SimulationConfig(
        seed=42,
        workflow_count=120,
        incident_scenario=scenario,
        incident_duration_workflows=60,
    )
    sim = TraceSimulator(cfg)
    result = sim.run()

    assert len(result.incidents) == 1
    inc = result.incidents[0]
    assert inc.scenario_type == scenario
    assert len(inc.affected_services) > 0
    assert len(inc.ground_truth_root_cause) > 0
    assert inc.ended_at is not None
    assert inc.started_at < inc.ended_at


def test_database_latency_causal_propagation():
    """Verify database degradation impacts dependent customer/inventory/payment services."""
    sampler = DeterministicSampler(seed=42)
    engine = IncidentEngine(sampler=sampler, incident_scenario=IncidentScenario.DATABASE_LATENCY)
    engine.plan_incidents(total_workflows=100, base_time=datetime.now(UTC))

    # Test modifier in active incident window (e.g. index 30)
    db_mod = engine.get_active_modifiers(30, "database-service")
    customer_mod = engine.get_active_modifiers(30, "customer-service")
    payment_mod = engine.get_active_modifiers(30, "payment-service")

    assert db_mod.latency_multiplier >= 5.0
    assert customer_mod.latency_multiplier >= 2.0
    assert payment_mod.latency_multiplier >= 2.0


def test_service_failure_triggers_workflow_failures():
    """Verify that hard service failure scenario generates failed workflows with exact reason."""
    cfg = SimulationConfig(
        seed=42,
        workflow_count=100,
        incident_scenario=IncidentScenario.SERVICE_FAILURE,
        incident_duration_workflows=40,
    )
    sim = TraceSimulator(cfg)
    result = sim.run()

    failed_execs = [e for e in result.executions if e.status == ExecutionStatus.FAILED]
    assert len(failed_execs) > 0
    # Verify failure reason explains inventory failure
    assert any("Inventory reservation failed" in (e.failure_reason or "") for e in failed_execs)
