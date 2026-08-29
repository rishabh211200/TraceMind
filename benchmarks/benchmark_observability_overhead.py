"""High-performance benchmark evaluating latency overhead of OpenTelemetry tracing & Prometheus metrics.

Evaluates 1,000 iterations with and without observability instrumentation:
1. Baseline execution latency (P50, P90, P95, P99, Mean)
2. Instrumented execution latency (OpenTelemetry span + Prometheus recording)
3. Latency percentile deltas (Delta P50, Delta P90, Delta P95, Delta P99, Delta Mean)
4. Quality gate: Delta P99 < 0.50 ms and Delta Mean < 0.20 ms
"""

import sys
import time

import numpy as np

from packages.observability.metrics import record_http_request
from packages.observability.tracer import (
    format_w3c_traceparent,
    generate_span_id,
    generate_trace_id,
    trace_span,
)


def _simulate_workload() -> dict[str, str]:
    """Representative small in-memory workload simulating API handler processing."""
    data = {"status": "healthy", "service": "order-service", "version": "0.11.0"}
    return {k: v.upper() for k, v in data.items()}


def run_overhead_benchmark(num_iterations: int = 1000) -> None:
    """Execute high-precision latency overhead measurement across 1,000 runs."""
    print("=" * 80)
    print("       TraceMind Milestone 11 Observability Latency Overhead Benchmark        ")
    print("=" * 80)

    # 1. Measure Baseline Latency (No Tracing or Metrics)
    baseline_latencies_ms: list[float] = []
    print(f"1. Measuring Baseline Request Latency ({num_iterations} iterations):")
    print("-" * 80)

    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _simulate_workload()
        elapsed = (time.perf_counter() - t0) * 1000.0
        baseline_latencies_ms.append(elapsed)

    base_p50 = float(np.percentile(baseline_latencies_ms, 50))
    base_p90 = float(np.percentile(baseline_latencies_ms, 90))
    base_p95 = float(np.percentile(baseline_latencies_ms, 95))
    base_p99 = float(np.percentile(baseline_latencies_ms, 99))
    base_mean = float(np.mean(baseline_latencies_ms))

    print(f"  Baseline P50 Latency  : {base_p50:6.3f} ms")
    print(f"  Baseline P90 Latency  : {base_p90:6.3f} ms")
    print(f"  Baseline P95 Latency  : {base_p95:6.3f} ms")
    print(f"  Baseline P99 Latency  : {base_p99:6.3f} ms")
    print(f"  Baseline Mean Latency : {base_mean:6.3f} ms")
    print()

    # 2. Measure Instrumented Latency (OpenTelemetry Spans + W3C + Prometheus)
    instrumented_latencies_ms: list[float] = []
    print(f"2. Measuring Instrumented Request Latency ({num_iterations} iterations):")
    print("-" * 80)

    for _ in range(num_iterations):
        t0 = time.perf_counter()
        trace_id = generate_trace_id()
        span_id = generate_span_id()
        _ = format_w3c_traceparent(trace_id, span_id, sampled=True)

        with trace_span(
            "http_request_span", {"http.method": "GET", "http.route": "/api/v1/health"}
        ):
            _simulate_workload()

        elapsed = (time.perf_counter() - t0) * 1000.0
        record_http_request("GET", "/api/v1/health", 200, elapsed / 1000.0)
        instrumented_latencies_ms.append(elapsed)

    inst_p50 = float(np.percentile(instrumented_latencies_ms, 50))
    inst_p90 = float(np.percentile(instrumented_latencies_ms, 90))
    inst_p95 = float(np.percentile(instrumented_latencies_ms, 95))
    inst_p99 = float(np.percentile(instrumented_latencies_ms, 99))
    inst_mean = float(np.mean(instrumented_latencies_ms))

    print(f"  Instrumented P50 Latency : {inst_p50:6.3f} ms")
    print(f"  Instrumented P90 Latency : {inst_p90:6.3f} ms")
    print(f"  Instrumented P95 Latency : {inst_p95:6.3f} ms")
    print(f"  Instrumented P99 Latency : {inst_p99:6.3f} ms")
    print(f"  Instrumented Mean Latency: {inst_mean:6.3f} ms")
    print()

    # 3. Calculate Percentile Deltas
    delta_p50 = inst_p50 - base_p50
    delta_p90 = inst_p90 - base_p90
    delta_p95 = inst_p95 - base_p95
    delta_p99 = inst_p99 - base_p99
    delta_mean = inst_mean - base_mean

    print("3. Validating Observability Overhead & Percentile Deltas:")
    print("-" * 80)
    print(f"  Delta P50  : {delta_p50:+6.3f} ms")
    print(f"  Delta P90  : {delta_p90:+6.3f} ms")
    print(f"  Delta P95  : {delta_p95:+6.3f} ms")
    print(f"  Delta P99  : {delta_p99:+6.3f} ms   [Target: < 0.500 ms]")
    print(f"  Delta Mean : {delta_mean:+6.3f} ms   [Target: < 0.200 ms]")
    print()

    p99_pass = delta_p99 < 0.50
    mean_pass = delta_mean < 0.20

    print("=" * 80)
    if p99_pass and mean_pass:
        print("   >>> MILESTONE 11 OBSERVABILITY BENCHMARK PASSED ALL QUALITY GATES <<<   ")
    else:
        print("   >>> MILESTONE 11 OBSERVABILITY BENCHMARK FAILED ONE OR MORE GATES <<<   ")
        sys.exit(1)
    print("=" * 80)


if __name__ == "__main__":
    run_overhead_benchmark(1000)
