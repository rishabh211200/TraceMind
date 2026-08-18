"""Regression invariant tests for seed-42 baseline simulation."""

from apps.simulator.config import SimulationConfig
from apps.simulator.stats import SimulationStats
from apps.simulator.workflow_engine import TraceSimulator
from packages.domain.workflow import ExecutionStatus


def test_seed_42_invariants_and_stability():
    """Verify core statistical invariants on a baseline 200-workflow generation."""
    config = SimulationConfig(
        seed=42,
        workflow_count=200,
        incident_probability=0.0,
    )
    simulator = TraceSimulator(config)
    result = simulator.run()
    stats = SimulationStats(result)

    # Invariant 1: Total counts
    assert stats.total_workflows == 200
    assert stats.successful_workflows + stats.failed_workflows == 200

    # Invariant 2: Latency percentiles monotonic ordering
    assert stats.min_latency_ms <= stats.median_latency_ms
    assert stats.median_latency_ms <= stats.p90_latency_ms
    assert stats.p90_latency_ms <= stats.p95_latency_ms
    assert stats.p95_latency_ms <= stats.p99_latency_ms
    assert stats.p99_latency_ms <= stats.max_latency_ms

    # Invariant 3: Nominal success rate under healthy conditions should be high (>90%)
    assert stats.success_rate >= 90.0

    # Invariant 4: Monotonic timestamps and span linkage
    for execution in result.executions:
        assert execution.completed_at is not None
        assert execution.started_at < execution.completed_at
        if execution.status == ExecutionStatus.COMPLETED:
            assert execution.error_count == 0
            assert execution.failure_reason is None
        elif execution.status == ExecutionStatus.FAILED:
            assert execution.error_count >= 1
            assert execution.failure_reason is not None
