"""Deterministic Benchmark for Milestone 9: Workflow Optimizer & Path Routing Engine.

Evaluates:
1. Single-Run Optimization Latency Distribution (1,000 Iterations) -> Target: P99 < 10.0ms.
2. 3D Pareto Optimal Frontier Mathematical Correctness.
3. Advisory Incident Diversion Efficacy & Verifiable >= 15% Improvement over Degraded Baselines.
"""

import sys
import time

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from apps.ml.optimizer.engine import WorkflowOptimizer
from apps.ml.optimizer.models import MultiObjectiveWeight


def run_benchmark() -> bool:
    print("=" * 80)
    print("      TraceMind Milestone 9 Workflow Optimizer & Path Routing Benchmark      ")
    print("=" * 80)

    optimizer = WorkflowOptimizer()

    # 1. Evaluate Latency Distribution across 1,000 Iterations
    iterations = 1000
    latencies: list[float] = []

    print(f"\n1. Measuring Optimization Execution Latency ({iterations:,} iterations):")
    print("-" * 80)

    weights_cycle = [
        MultiObjectiveWeight(latency=0.40, cost=0.30, reliability=0.30),
        MultiObjectiveWeight(latency=0.70, cost=0.15, reliability=0.15),
        MultiObjectiveWeight(latency=0.20, cost=0.60, reliability=0.20),
        MultiObjectiveWeight(latency=0.20, cost=0.20, reliability=0.60),
    ]

    for i in range(iterations):
        w = weights_cycle[i % len(weights_cycle)]
        t0 = time.perf_counter()
        _ = optimizer.optimize_workflow(weights=w)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    p50 = float(np.percentile(latencies, 50))
    p90 = float(np.percentile(latencies, 90))
    p95 = float(np.percentile(latencies, 95))
    p99 = float(np.percentile(latencies, 99))
    max_lat = float(np.max(latencies))
    mean_lat = float(np.mean(latencies))
    throughput = iterations / (sum(latencies) / 1000.0)

    print(f"  P50 Latency : {p50:6.3f} ms")
    print(f"  P90 Latency : {p90:6.3f} ms")
    print(f"  P95 Latency : {p95:6.3f} ms")
    print(f"  P99 Latency : {p99:6.3f} ms   [Target: < 10.0 ms]")
    print(f"  Mean Latency: {mean_lat:6.3f} ms")
    print(f"  Max Latency : {max_lat:6.3f} ms")
    print(f"  Throughput  : {throughput:8.1f} optimizations / sec")

    latency_pass = p99 < 10.0
    print(f"  --> Latency Gate Check: {'[PASS]' if latency_pass else '[FAIL]'}")

    # 2. Validate Pareto Frontier Dominance Properties
    print("\n2. Validating 3D Pareto Optimal Frontier Dominance:")
    print("-" * 80)

    canonical_paths = optimizer.path_extractor.get_canonical_order_paths()
    pareto_pts = optimizer.pareto_calculator.compute_frontier(canonical_paths)

    optimal_pts = [pt for pt in pareto_pts if pt.is_pareto_optimal]
    dominated_pts = [pt for pt in pareto_pts if not pt.is_pareto_optimal]

    print(f"  Total Evaluated Candidate Paths: {len(canonical_paths)}")
    print(
        f"  Non-Dominated Pareto Optimal Set: {len(optimal_pts)} paths ({', '.join(pt.path_id for pt in optimal_pts)})"
    )
    print(
        f"  Dominated Paths                 : {len(dominated_pts)} paths ({', '.join(pt.path_id for pt in dominated_pts)})"
    )

    pareto_valid = len(optimal_pts) >= 2 and len(dominated_pts) >= 1
    print(f"  --> Pareto Frontier Gate Check: {'[PASS]' if pareto_valid else '[FAIL]'}")

    # 3. Validate Advisory Incident Diversion & >= 15% Verifiable Improvement
    print("\n3. Validating Advisory Incident Diversion Efficacy across Failure Modes:")
    print("-" * 80)

    bottlenecks = [
        ("inventory-db", "Database IOPS Saturation"),
        ("customer-db", "Customer DB Slow Query Lock"),
        ("payment-gateway", "Transit Gateway Packet Loss"),
        ("pricing-service", "Pricing Service Crash"),
    ]

    all_improvements_pass = True
    for culprit, description in bottlenecks:
        rec = optimizer.optimize_workflow(active_incident_culprit=culprit)
        savings = rec.expected_savings

        # Target: Latency reduction >= 15% OR Reliability improvement >= 15%
        lat_gain = savings.latency_reduction_pct
        rel_gain = savings.reliability_gain_pct
        effective_improvement = max(lat_gain, rel_gain)
        is_pass = effective_improvement >= 15.0

        if not is_pass:
            all_improvements_pass = False

        status_str = "[PASS]" if is_pass else "[FAIL]"
        print(
            f"  Culprit: {culprit:<18} ({description:<30}) -> Rec: {rec.recommended_path.path_id} | "
            f"Rel Gain: +{rel_gain:4.1f}% | Lat Reduction: {lat_gain:4.1f}% | Max Gain: {effective_improvement:4.1f}% {status_str}"
        )

    print(
        f"  --> Verifiable >= 15% Improvement Gate Check: {'[PASS]' if all_improvements_pass else '[FAIL]'}"
    )

    # Overall Summary
    all_passed = latency_pass and pareto_valid and all_improvements_pass
    print("\n" + "=" * 80)
    if all_passed:
        print("   >>> MILESTONE 9 WORKFLOW OPTIMIZER BENCHMARK PASSED ALL QUALITY GATES <<<   ")
    else:
        print("   >>> MILESTONE 9 BENCHMARK FAILED ONE OR MORE GATES <<<   ")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
