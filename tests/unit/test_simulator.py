"""Unit tests for TraceSim discrete-event simulation engine and components."""

from apps.simulator.config import ServiceConfig, SimulationConfig
from apps.simulator.distributions import DeterministicSampler
from apps.simulator.incidents import IncidentEngine
from apps.simulator.services import SimulatedService
from apps.simulator.workflow_engine import TraceSimulator
from packages.domain.events import EventType


def test_sampler_determinism():
    """Verify that two samplers with the same seed produce identical sequences."""
    s1 = DeterministicSampler(seed=123)
    s2 = DeterministicSampler(seed=123)

    latencies_1 = [s1.sample_latency(50.0) for _ in range(50)]
    latencies_2 = [s2.sample_latency(50.0) for _ in range(50)]
    assert latencies_1 == latencies_2

    bools_1 = [s1.sample_bernoulli(0.3) for _ in range(50)]
    bools_2 = [s2.sample_bernoulli(0.3) for _ in range(50)]
    assert bools_1 == bools_2


def test_service_nominal_execution():
    """Verify basic service execution emits start and completed events."""
    sampler = DeterministicSampler(seed=42)
    incident_engine = IncidentEngine(sampler=sampler, incident_probability=0.0)
    cfg = ServiceConfig(name="auth-service", baseline_latency_ms=25.0, baseline_failure_rate=0.0)
    service = SimulatedService(config=cfg, sampler=sampler, incident_engine=incident_engine)

    from datetime import UTC, datetime

    res = service.execute(
        operation="authenticate_user",
        workflow_index=0,
        execution_id="exec_test_001",
        workflow_id="order_flow",
        correlation_id="corr_test_001",
        sim_start_time=datetime.now(UTC),
    )

    assert res.success is True
    assert res.retry_count == 0
    assert len(res.events) == 2
    assert res.events[0].event_type == EventType.SERVICE_STARTED
    assert res.events[1].event_type == EventType.SERVICE_COMPLETED


def test_service_timeout_handling():
    """Verify that operations exceeding timeout threshold trigger timeout events."""
    sampler = DeterministicSampler(seed=42)
    incident_engine = IncidentEngine(sampler=sampler, incident_probability=0.0)
    cfg = ServiceConfig(
        name="slow-service",
        baseline_latency_ms=500.0,
        timeout_ms=50.0,  # Strict timeout guaranteed to trigger
        max_retries=0,
        baseline_failure_rate=0.0,
    )
    service = SimulatedService(config=cfg, sampler=sampler, incident_engine=incident_engine)

    from datetime import UTC, datetime

    res = service.execute(
        operation="slow_op",
        workflow_index=0,
        execution_id="exec_timeout_001",
        workflow_id="order_flow",
        correlation_id="corr_timeout_001",
        sim_start_time=datetime.now(UTC),
    )

    assert res.success is False
    assert res.is_timeout is True
    assert any(ev.event_type == EventType.SERVICE_TIMEOUT for ev in res.events)


def test_service_retry_mechanism():
    """Verify retry attempts and backoff events upon transient failures."""
    sampler = DeterministicSampler(seed=42)
    incident_engine = IncidentEngine(sampler=sampler, incident_probability=0.0)
    cfg = ServiceConfig(
        name="flaky-service",
        baseline_latency_ms=20.0,
        baseline_failure_rate=1.0,  # Force initial failures
        max_retries=2,
        retry_backoff_ms=30.0,
    )
    service = SimulatedService(config=cfg, sampler=sampler, incident_engine=incident_engine)

    from datetime import UTC, datetime

    res = service.execute(
        operation="flaky_op",
        workflow_index=0,
        execution_id="exec_retry_001",
        workflow_id="order_flow",
        correlation_id="corr_retry_001",
        sim_start_time=datetime.now(UTC),
    )

    assert res.success is False
    assert res.retry_count == 2
    # Verify retry events were recorded
    retry_started_events = [e for e in res.events if e.event_type == EventType.RETRY_STARTED]
    assert len(retry_started_events) == 2


def test_trace_simulator_determinism():
    """Verify complete simulation run is strictly reproducible given identical seed."""
    cfg1 = SimulationConfig(seed=999, workflow_count=100, incident_probability=0.0)
    sim1 = TraceSimulator(cfg1)
    res1 = sim1.run()

    cfg2 = SimulationConfig(seed=999, workflow_count=100, incident_probability=0.0)
    sim2 = TraceSimulator(cfg2)
    res2 = sim2.run()

    assert len(res1.executions) == len(res2.executions) == 100
    assert len(res1.events) == len(res2.events)

    for e1, e2 in zip(res1.executions, res2.executions, strict=False):
        assert e1.id == e2.id
        assert e1.status == e2.status
        assert e1.total_latency_ms == e2.total_latency_ms
        assert e1.retry_count == e2.retry_count

    for ev1, ev2 in zip(res1.events, res2.events, strict=False):
        assert ev1.event_id == ev2.event_id
        assert ev1.event_type == ev2.event_type
        assert ev1.latency_ms == ev2.latency_ms
