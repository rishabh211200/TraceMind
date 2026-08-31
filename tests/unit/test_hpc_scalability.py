"""Unit tests for high-performance multiprocessing simulation and profiler."""

import pytest

from apps.simulator.parallel_engine import MultiprocessTraceSimulator
from packages.common.profiler import (
    PerformanceProfiler,
    discover_system_hardware,
    profile_section,
)


def test_discover_system_hardware():
    """Verify hardware discovery returns expected fields."""
    specs = discover_system_hardware()
    assert specs.logical_cores >= 1
    assert specs.total_ram_gb > 0.0
    assert len(specs.python_version) > 0
    assert len(specs.os_name) > 0
    d = specs.to_dict()
    assert "logical_cores" in d
    assert "total_ram_gb" in d


def test_performance_profiler_statistics():
    """Verify profiler calculates exact percentiles and throughput."""
    prof = PerformanceProfiler(name="UnitTestProfiler", total_items=100, parallel_workers=2).start()
    for val in range(1, 101):
        prof.record_item_latency(float(val))

    res = prof.stop(speedup_vs_baseline=1.8)
    assert res.total_items == 100
    assert res.p50_latency_ms == pytest.approx(50.5, abs=1.0)
    assert res.p90_latency_ms == pytest.approx(90.1, abs=1.0)
    assert res.p99_latency_ms == pytest.approx(99.01, abs=1.0)
    assert res.min_latency_ms == 1.0
    assert res.max_latency_ms == 100.0
    assert res.parallel_workers == 2
    assert res.speedup_vs_baseline == 1.8
    assert res.parallel_efficiency_pct == pytest.approx(90.0, abs=1.0)


def test_profile_section_context_manager():
    """Verify profile_section context manager works cleanly."""
    with profile_section("SectionTest", total_items=10) as prof:
        prof.record_item_latency(5.0)
        prof.record_item_latency(10.0)


def test_multiprocess_simulator_single_worker():
    """Verify MultiprocessTraceSimulator with 1 worker produces expected results."""
    sim = MultiprocessTraceSimulator(base_seed=42)
    res = sim.run_parallel(total_executions=20, chunk_size=10, workers=1)
    assert res.total_executions == 20
    assert res.total_events > 0
    assert res.workers_used == 1
    assert res.throughput_executions_per_sec > 0


def test_multiprocess_simulator_multi_worker():
    """Verify MultiprocessTraceSimulator with 2 workers produces deterministic output."""
    sim = MultiprocessTraceSimulator(base_seed=42)
    res = sim.run_parallel(total_executions=40, chunk_size=10, workers=2)
    assert res.total_executions == 40
    assert res.total_events > 0
    assert res.workers_used == 2
    assert res.num_chunks == 4


def test_multiprocess_simulator_stream_chunks():
    """Verify stream_chunks yields sequential chunks without error."""
    sim = MultiprocessTraceSimulator(base_seed=42)
    chunks_seen = 0
    total_execs = 0
    for _chunk_idx, execs, events in sim.stream_chunks(total_executions=30, chunk_size=10):
        chunks_seen += 1
        total_execs += len(execs)
        assert len(execs) == 10
        assert len(events) > 0

    assert chunks_seen == 3
    assert total_execs == 30
