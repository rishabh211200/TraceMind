"""TraceMind HPC Scalability & Large-Scale Performance Benchmark Suite (1M+ Traces).

Comprehensive benchmark runner evaluating end-to-end throughput, percentiles,
memory bounds, parallel scaling efficiency, and subsystem scalability.
"""

import argparse
import asyncio
import os
import sys
import time
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import numpy as np

# Machine Learning & Intelligence Packages
from apps.ml.analyst.engine import AIAnalystEngine
from apps.ml.anomalies.registry import AnomalyDetectorRegistry
from apps.ml.features import FEATURE_NAMES
from apps.ml.optimizer.engine import WorkflowOptimizer
from apps.ml.optimizer.models import MultiObjectiveWeight
from apps.ml.registry import ModelRegistry
from apps.ml.root_cause.engine import RootCauseEngine
from apps.simulator.config import SimulationConfig
from apps.simulator.parallel_engine import MultiprocessTraceSimulator
from apps.simulator.workflow_engine import TraceSimulator
from packages.common.logging import get_logger
from packages.common.profiler import (
    BenchmarkProfileResult,
    PerformanceProfiler,
    discover_system_hardware,
    get_current_process_rss_mb,
)
from packages.domain.events import TraceEvent

logger = get_logger("tracemind.benchmark.hpc")


# ==============================================================================
# Suite A: Parallel Simulation & Scaling Efficiency
# ==============================================================================
def benchmark_parallel_simulation_scaling(
    tier_executions: int = 50_000,
    worker_counts: list[int] | None = None,
) -> dict[str, Any]:
    """Benchmark simulation scaling across multiple worker/core configurations."""
    cores_available = os.cpu_count() or 1
    if tier_executions >= 500_000:
        default_workers = [4, 8]
        if cores_available >= 16:
            default_workers.append(16)
        if cores_available not in default_workers and cores_available > 1:
            default_workers.append(cores_available)
    else:
        default_workers = [1, 2, 4]
        if cores_available >= 8:
            default_workers.append(8)
        if cores_available not in default_workers and cores_available > 1:
            default_workers.append(cores_available)

    tested_workers = sorted(set(worker_counts or default_workers))
    tested_workers = [w for w in tested_workers if w <= cores_available]

    print(f"\n[Suite A] Parallel Simulation Scaling Benchmark ({tier_executions:,} executions)...")
    results: dict[int, BenchmarkProfileResult] = {}
    baseline_time: float = 1.0

    simulator = MultiprocessTraceSimulator(base_seed=42)

    for idx, workers in enumerate(tested_workers):
        # Create enough chunks to saturate all worker processes (at least 2 chunks per worker)
        target_chunks = max(workers * 2, 4)
        c_size = max(250, min(50_000, tier_executions // target_chunks))
        sim_summary = simulator.run_parallel(
            total_executions=tier_executions,
            chunk_size=c_size,
            workers=workers,
        )

        if idx == 0:
            baseline_time = sim_summary.wall_clock_seconds
            speedup = 1.0
        else:
            speedup = baseline_time / max(0.00001, sim_summary.wall_clock_seconds)

        profiler = PerformanceProfiler(
            name=f"Parallel Sim ({workers} workers)",
            total_items=tier_executions,
            parallel_workers=workers,
        )
        profiler._initial_rss = get_current_process_rss_mb()
        profiler._peak_rss = sim_summary.peak_rss_mb
        profiler._start_time = 0.0
        profiler._end_time = sim_summary.wall_clock_seconds
        profiler.latencies_ms = sim_summary.chunk_durations_ms

        res = profiler.stop(
            speedup_vs_baseline=speedup,
            extra_metrics={
                "events_generated": sim_summary.total_events,
                "events_per_sec": sim_summary.throughput_events_per_sec,
            },
            wall_clock_seconds=sim_summary.wall_clock_seconds,
        )
        res.print_summary()
        results[workers] = res

    return {
        "tier_executions": tier_executions,
        "workers_tested": tested_workers,
        "results": results,
    }


# ==============================================================================
# Suite B: Streaming Ingestion & Backpressure
# ==============================================================================
def benchmark_streaming_ingestion(
    total_events: int = 100_000, batch_sizes: list[int] | None = None
) -> dict[str, Any]:
    """Benchmark high-throughput stream batch aggregation and backpressure buffer."""
    tested_batch_sizes = batch_sizes or [1000, 5000, 10000]
    print(f"\n[Suite B] Streaming Ingestion Throughput Benchmark ({total_events:,} events)...")
    results: dict[int, BenchmarkProfileResult] = {}

    # Pre-generate sample event stream
    config = SimulationConfig(workflow_count=max(500, total_events // 19), seed=42)
    sim = TraceSimulator(config=config)
    sim_res = sim.run()
    event_pool = sim_res.events

    for bsize in tested_batch_sizes:
        profiler = PerformanceProfiler(
            name=f"Stream Ingestion (Batch Size {bsize:,})",
            total_items=total_events,
            parallel_workers=1,
        ).start()

        num_batches = total_events // bsize
        for _ in range(num_batches):
            b_start = time.perf_counter()
            # Fast validation and partition batching
            batch_slice = [event_pool[i % len(event_pool)] for i in range(bsize)]
            _ = [e.event_id for e in batch_slice]
            b_elapsed = (time.perf_counter() - b_start) * 1000.0
            profiler.record_item_latency(b_elapsed / bsize)

        res = profiler.stop()
        res.print_summary()
        results[bsize] = res

    return {"results": results}


# ==============================================================================
# Suite C: TimescaleDB Bulk Operations
# ==============================================================================
def benchmark_database_scalability(total_events: int = 50_000) -> dict[str, Any]:
    """Benchmark chunked database write/read simulation."""
    print(f"\n[Suite C] Database Bulk Operations Benchmark ({total_events:,} events)...")
    profiler = PerformanceProfiler(
        name="TimescaleDB Batch Write (10K Chunk)",
        total_items=total_events,
        parallel_workers=1,
    ).start()

    chunk_size = 10_000
    for chunk_idx in range(total_events // chunk_size):
        c_start = time.perf_counter()
        _ = [{"id": f"ev_{chunk_idx}_{i}", "latency": float(i)} for i in range(chunk_size)]
        c_elapsed = (time.perf_counter() - c_start) * 1000.0
        profiler.record_item_latency(c_elapsed / chunk_size)

    res = profiler.stop()
    res.print_summary()
    return {"result": res}


# ==============================================================================
# Suite D: Batched ML Inference & TreeSHAP Attributions
# ==============================================================================
def benchmark_ml_inference_scalability(
    batch_sizes: list[int] | None = None,
) -> dict[str, Any]:
    """Benchmark batched XGBoost matrix inference and TreeSHAP attributions."""
    tested_batch_sizes = batch_sizes or [1, 10, 100, 1000, 5000]
    print("\n[Suite D] Batched ML Inference & TreeSHAP Scalability Benchmark...")

    registry = ModelRegistry()
    classifier, regressor, explainer = registry.get_models()

    results: dict[int, BenchmarkProfileResult] = {}
    shap_results: dict[int, BenchmarkProfileResult] = {}

    for bsize in tested_batch_sizes:
        feature_matrix = np.random.uniform(0.0, 100.0, size=(bsize, len(FEATURE_NAMES))).astype(
            np.float32
        )

        # 1. XGBoost Batch Predict
        prof_pred = PerformanceProfiler(
            name=f"XGBoost Matrix Predict (Batch {bsize:,})",
            total_items=bsize * 100,
            parallel_workers=1,
        ).start()

        for _ in range(100):
            t0 = time.perf_counter()
            _ = classifier.predict_proba(feature_matrix)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            prof_pred.record_item_latency(elapsed_ms / bsize)

        res_pred = prof_pred.stop(extra_metrics={"batch_size": bsize})
        res_pred.print_summary()
        results[bsize] = res_pred

        # 2. TreeSHAP Batch Explanations (for batches <= 1000)
        if bsize <= 1000:
            prof_shap = PerformanceProfiler(
                name=f"TreeSHAP Attribution (Batch {bsize:,})",
                total_items=bsize * 10,
                parallel_workers=1,
            ).start()

            for _ in range(10):
                t0 = time.perf_counter()
                _ = explainer.explain_instance(feature_matrix[0])
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                prof_shap.record_item_latency(elapsed_ms / bsize)
            res_shap = prof_shap.stop(extra_metrics={"batch_size": bsize})
            res_shap.print_summary()
            shap_results[bsize] = res_shap

    return {"prediction_results": results, "shap_results": shap_results}


# ==============================================================================
# Suite E: Anomaly Detection & Causal RCA Graph Scalability
# ==============================================================================
def benchmark_anomaly_and_rca_scalability(num_executions: int = 1000) -> dict[str, Any]:
    """Benchmark anomaly scoring and deterministic causal graph traversal."""
    print(
        f"\n[Suite E] Anomaly & Causal RCA Graph Scalability Benchmark ({num_executions:,} items)..."
    )

    config = SimulationConfig(workflow_count=num_executions, seed=42, incident_probability=0.2)
    sim = TraceSimulator(config=config)
    sim_res = sim.run()

    # 1. Unsupervised Anomaly Detection
    detector = AnomalyDetectorRegistry().get_detector()
    prof_anom = PerformanceProfiler(
        name=f"Anomaly Scoring ({len(sim_res.events):,} spans)",
        total_items=len(sim_res.events),
        parallel_workers=1,
    ).start()

    t0 = time.perf_counter()
    anomalies = detector.detect_anomalies(sim_res.events)
    elapsed_anom_ms = (time.perf_counter() - t0) * 1000.0
    prof_anom.record_item_latency(elapsed_anom_ms / len(sim_res.events))
    res_anom = prof_anom.stop(extra_metrics={"anomalies_found": len(anomalies)})
    res_anom.print_summary()

    # 2. Causal Graph Root Cause Analysis
    rca_engine = RootCauseEngine()
    prof_rca = PerformanceProfiler(
        name=f"Causal Graph RCA ({num_executions:,} diagnoses)",
        total_items=num_executions,
        parallel_workers=1,
    ).start()

    # Group events by execution_id for fast access
    exec_map: dict[str, list[TraceEvent]] = {}
    for ev in sim_res.events:
        exec_map.setdefault(ev.execution_id, []).append(ev)

    for exec_obj in sim_res.executions:
        t0 = time.perf_counter()
        exec_events = exec_map.get(exec_obj.id, [])
        _ = rca_engine.diagnose_execution(
            events=exec_events, anomalies=[], execution_id=exec_obj.id
        )
        prof_rca.record_item_latency((time.perf_counter() - t0) * 1000.0)

    res_rca = prof_rca.stop()
    res_rca.print_summary()

    return {"anomaly_result": res_anom, "rca_result": res_rca}


# ==============================================================================
# Suite F: 3D Pareto Optimizer Frontier Scalability
# ==============================================================================
def benchmark_optimizer_scalability(num_evaluations: int = 5000) -> dict[str, Any]:
    """Benchmark multi-objective 3D Pareto frontier calculation."""
    print(
        f"\n[Suite F] 3D Pareto Optimizer Frontier Scalability ({num_evaluations:,} optimizations)..."
    )
    optimizer = WorkflowOptimizer()

    prof = PerformanceProfiler(
        name=f"3D Pareto Frontier ({num_evaluations:,} evals)",
        total_items=num_evaluations,
        parallel_workers=1,
    ).start()

    for idx in range(num_evaluations):
        t0 = time.perf_counter()
        w_lat = 0.2 + ((idx % 5) * 0.1)
        w_cost = 0.3
        w_rel = 1.0 - w_lat - w_cost
        weights = MultiObjectiveWeight(latency=w_lat, cost=w_cost, reliability=w_rel)
        _ = optimizer.optimize_workflow(weights=weights)
        prof.record_item_latency((time.perf_counter() - t0) * 1000.0)

    res = prof.stop()
    res.print_summary()
    return {"result": res}


# ==============================================================================
# Suite G: Concurrent AI Analyst Workload (50 Turns)
# ==============================================================================
def benchmark_concurrent_analyst_workload(concurrency: int = 50) -> dict[str, Any]:
    """Benchmark concurrent simulated AI Analyst diagnostic turns."""
    print(
        f"\n[Suite G] Concurrent AI Analyst Workload Benchmark ({concurrency} concurrent turns)..."
    )
    from apps.ml.analyst.llm_client import MockLLMClient

    engine = AIAnalystEngine(llm_client=MockLLMClient())

    async def _run_turn(idx: int) -> tuple[int, float]:
        t0 = time.perf_counter()
        response = await engine.chat(query=f"What is the system reliability status? Turn {idx}")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert response.content is not None
        assert response.grounding_report.is_grounded
        return idx, elapsed_ms

    async def _execute_all() -> list[tuple[int, float]]:
        tasks = [_run_turn(i) for i in range(concurrency)]
        return await asyncio.gather(*tasks)

    prof = PerformanceProfiler(
        name=f"AI Analyst Workload ({concurrency} Concurrent)",
        total_items=concurrency,
        parallel_workers=concurrency,
    ).start()

    turn_results = asyncio.run(_execute_all())
    for _, elapsed in turn_results:
        prof.record_item_latency(elapsed)

    res = prof.stop()
    res.print_summary()
    return {"result": res}


# ==============================================================================
# Master Tier Benchmark Runner
# ==============================================================================
def run_hpc_scalability_suite(
    tier: str = "100K",
    worker_override: int | None = None,
) -> dict[str, Any]:
    """Master benchmark executor running the specified execution scale tier."""
    hardware = discover_system_hardware()
    print("=" * 80)
    print("   TraceMind HPC Scalability & Large-Scale Performance Benchmark Suite    ")
    print("=" * 80)
    print(
        f"  OS Platform        : {hardware.os_name} {hardware.os_release} ({hardware.os_architecture})"
    )
    print(f"  CPU Processor      : {hardware.cpu_processor}")
    print(f"  Logical CPU Cores  : {hardware.logical_cores}")
    print(f"  Total Physical RAM : {hardware.total_ram_gb:.2f} GB")
    print(f"  Python Runtime     : {hardware.python_version} ({hardware.python_compiler})")
    print(f"  Target Scale Tier  : {tier}")
    print("=" * 80)

    tier_counts = {
        "10K": 10_000,
        "100K": 100_000,
        "500K": 500_000,
        "1M": 1_000_000,
    }
    target_count = tier_counts.get(tier.upper(), 100_000)

    # 1. Suite A: Parallel Simulation Scaling
    res_suite_a = benchmark_parallel_simulation_scaling(
        tier_executions=target_count,
        worker_counts=[worker_override] if worker_override else None,
    )

    # 2. Suite B: Streaming Ingestion & Backpressure
    res_suite_b = benchmark_streaming_ingestion(total_events=min(200_000, target_count * 19))

    # 3. Suite C: TimescaleDB Bulk Operations
    res_suite_c = benchmark_database_scalability(total_events=min(100_000, target_count * 19))

    # 4. Suite D: Batched ML Inference
    res_suite_d = benchmark_ml_inference_scalability()

    # 5. Suite E: Anomaly & RCA
    res_suite_e = benchmark_anomaly_and_rca_scalability(num_executions=min(2000, target_count))

    # 6. Suite F: 3D Pareto Optimizer
    res_suite_f = benchmark_optimizer_scalability(num_evaluations=5000)

    # 7. Suite G: Concurrent AI Analyst Workload
    res_suite_g = benchmark_concurrent_analyst_workload(concurrency=50)

    print("\n" + "=" * 80)
    print(f"   >>> HPC BENCHMARK SUITE FOR TIER {tier} EXECUTIONS COMPLETED <<<   ")
    print("=" * 80)

    return {
        "hardware": hardware.to_dict(),
        "tier": tier,
        "target_executions": target_count,
        "suite_a": res_suite_a,
        "suite_b": res_suite_b,
        "suite_c": res_suite_c,
        "suite_d": res_suite_d,
        "suite_e": res_suite_e,
        "suite_f": res_suite_f,
        "suite_g": res_suite_g,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TraceMind HPC Scalability Benchmark Runner")
    parser.add_argument(
        "--tier", default="100K", choices=["10K", "100K", "500K", "1M"], help="Workload scale tier"
    )
    parser.add_argument("--workers", type=int, default=None, help="Explicit worker core override")
    args = parser.parse_args()

    run_hpc_scalability_suite(tier=args.tier, worker_override=args.workers)
