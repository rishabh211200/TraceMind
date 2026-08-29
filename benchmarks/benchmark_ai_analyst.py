"""Performance, Grounding Accuracy, and Latency Benchmark for Tool-Grounded AI Analyst.

Evaluates 100 multi-intent diagnostic queries across 7 canonical fault scenarios:
1. Tool dispatch and ReAct loop latency (P50, P90, P95, P99)
2. Grounding verification rate (Target >= 95.0%)
3. Hallucination rate (Target 0.0% unverified service names)
4. Overall throughput (queries / sec)
"""

import asyncio
import sys
import time

import numpy as np

from apps.ml.analyst.engine import AIAnalystEngine
from apps.ml.analyst.guardrails import KNOWN_SERVICES
from apps.ml.analyst.models import LLMConfig

BENCHMARK_QUERIES = [
    "What caused the failure in order_fulfillment execution exec_4a9b?",
    "Why did payment-service experience high latency in execution exec_7c2d?",
    "Diagnose the root culprit behind database IOPS saturation in exec_db_01.",
    "Explain the in-flight failure risk and TreeSHAP attributions for execution exec_4a9b.",
    "Which features contributed most to the latency spike in exec_shap_test?",
    "What optimal routing detour does the optimizer recommend around inventory-db?",
    "Suggest a fallback path for payment-gateway with minimal cost and latency.",
    "How does the optimizer balance latency vs cost vs reliability for order_fulfillment?",
    "Show me the system microservice dependency topology and operational health.",
    "Which microservices are managed in the order_fulfillment workflow?",
    "Query unsupervised anomaly detection scores for execution exec_anom_01.",
    "Were any Isolation Forest or Autoencoder anomalies detected during the outage?",
    "Fetch the span execution DAG tree for execution exec_tree_01.",
    "What was the total latency and span breakdown for exec_4a9b?",
]


async def run_analyst_benchmark(num_iterations: int = 100) -> None:
    """Execute high-performance AI Analyst grounding and latency benchmark."""
    print("=" * 80)
    print("        TraceMind Milestone 10 Tool-Grounded AI Analyst Benchmark        ")
    print("=" * 80)

    engine = AIAnalystEngine()
    cfg = LLMConfig(provider="mock")

    latencies_ms: list[float] = []
    grounding_scores: list[float] = []
    hallucination_counts: int = 0
    total_queries = 0

    print(f"1. Benchmarking Agentic Chat Execution Latency & Grounding ({num_iterations} queries):")
    print("-" * 80)

    start_total = time.perf_counter()

    for idx in range(num_iterations):
        query = BENCHMARK_QUERIES[idx % len(BENCHMARK_QUERIES)]
        t0 = time.perf_counter()
        resp = await engine.chat(query=query, conversation_id=f"conv_bench_{idx}", config=cfg)
        elapsed = (time.perf_counter() - t0) * 1000.0

        latencies_ms.append(elapsed)
        grounding_scores.append(resp.grounding_report.grounding_score)

        # Check for unverified service hallucinations
        for unverified in resp.grounding_report.unverified_claims:
            if "Unverified service" in unverified:
                hallucination_counts += 1

        total_queries += 1

    total_time_s = time.perf_counter() - start_total
    throughput = total_queries / total_time_s if total_time_s > 0 else 0.0

    p50 = float(np.percentile(latencies_ms, 50))
    p90 = float(np.percentile(latencies_ms, 90))
    p95 = float(np.percentile(latencies_ms, 95))
    p99 = float(np.percentile(latencies_ms, 99))
    mean_lat = float(np.mean(latencies_ms))
    max_lat = float(np.max(latencies_ms))
    avg_grounding = float(np.mean(grounding_scores)) * 100
    hallucination_rate = (hallucination_counts / total_queries) * 100

    print(f"  Total Queries Processed: {total_queries} in {total_time_s:.3f}s")
    print(f"  P50 Latency            : {p50:6.3f} ms")
    print(f"  P90 Latency            : {p90:6.3f} ms")
    print(f"  P95 Latency            : {p95:6.3f} ms")
    print(f"  P99 Latency            : {p99:6.3f} ms   [Target: < 25.0 ms]")
    print(f"  Mean Latency           : {mean_lat:6.3f} ms")
    print(f"  Max Latency            : {max_lat:6.3f} ms")
    print(f"  Throughput             : {throughput:8.1f} queries / sec")
    print(f"  --> Latency Gate Check : [{'PASS' if p99 < 25.0 else 'FAIL'}]")
    print()

    print("2. Validating Grounding Accuracy & Hallucination Guardrails:")
    print("-" * 80)
    print(f"  Average Grounding Score: {avg_grounding:6.2f}%  [Target: >= 95.0%]")
    print(f"  Service Hallucination Rate: {hallucination_rate:4.2f}%  [Target: 0.0%]")
    print(f"  Known Topology Services: {len(KNOWN_SERVICES)} microservices verified")
    print(
        f"  --> Grounding Gate Check: [{'PASS' if avg_grounding >= 95.0 and hallucination_rate == 0.0 else 'FAIL'}]"
    )
    print()

    print("=" * 80)
    if p99 < 25.0 and avg_grounding >= 95.0 and hallucination_rate == 0.0:
        print("   >>> MILESTONE 10 AI ANALYST BENCHMARK PASSED ALL QUALITY GATES <<<   ")
    else:
        print("   >>> MILESTONE 10 AI ANALYST BENCHMARK FAILED ONE OR MORE GATES <<<   ")
        sys.exit(1)
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_analyst_benchmark(100))
