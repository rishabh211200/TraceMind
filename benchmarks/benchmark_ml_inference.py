"""Performance and latency benchmark for ML In-Flight Feature Extraction and TreeSHAP Inference."""

import time
from datetime import UTC, datetime, timedelta

import numpy as np

from apps.ml.features import TraceFeatureExtractor
from apps.ml.registry import ModelRegistry
from packages.domain.events import EventStatus, EventType, TraceEvent


def _generate_synthetic_spans(num_spans: int = 6) -> list[TraceEvent]:
    base = datetime.now(UTC)
    services = [
        "auth-service",
        "customer-service",
        "customer-cache",
        "customer-db",
        "pricing-service",
        "payment-service",
    ]
    events = []
    for i in range(num_spans):
        svc = services[i % len(services)]
        events.append(
            TraceEvent(
                event_id=f"evt_{i}",
                execution_id="bench_exec_001",
                workflow_id="order_fulfillment",
                service=svc,
                operation="process",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS if i != 5 else EventStatus.FAILURE,
                latency_ms=25.0 if i != 5 else 850.0,
                timestamp=base + timedelta(milliseconds=i * 50),
            )
        )
    return events


def run_benchmark(num_iterations: int = 1000) -> None:
    print("=" * 80)
    print("        TraceMind Milestone 6 ML & TreeSHAP Inference Benchmark        ")
    print("=" * 80)

    # 1. Ensure models are trained / loaded
    registry = ModelRegistry()
    classifier, regressor, explainer = registry.get_models()
    extractor = TraceFeatureExtractor()

    spans = _generate_synthetic_spans(6)

    # 2. Benchmark Feature Extraction
    t0 = time.perf_counter()
    for _ in range(num_iterations):
        _ = extractor.extract_features_from_events(spans)
    feat_time = time.perf_counter() - t0
    feat_rate = num_iterations / feat_time

    # 3. Benchmark End-to-End Inference (Feature Extraction + XGBoost + TreeSHAP)
    latencies_ms: list[float] = []
    t_start = time.perf_counter()

    for _ in range(num_iterations):
        iter_t0 = time.perf_counter()
        feats = extractor.extract_features_from_events(spans)
        _prob, _risk = classifier.predict_single(feats)
        _lat = regressor.predict_single(feats)
        _contribs = explainer.explain_instance(feats, top_k=5)
        iter_time = (time.perf_counter() - iter_t0) * 1000.0
        latencies_ms.append(iter_time)

    total_time = time.perf_counter() - t_start
    total_rate = num_iterations / total_time

    p50 = float(np.percentile(latencies_ms, 50))
    p90 = float(np.percentile(latencies_ms, 90))
    p95 = float(np.percentile(latencies_ms, 95))
    p99 = float(np.percentile(latencies_ms, 99))
    mean_lat = float(np.mean(latencies_ms))

    print(f" Total Benchmark Inferences Processed : {num_iterations:,} runs")
    print("-" * 80)
    print(
        f" 1. Feature Extraction Throughput      : {feat_rate:,.0f} extractions/sec ({feat_time:.3f}s)"
    )
    print(
        f" 2. End-to-End Inference Throughput    : {total_rate:,.0f} inferences/sec ({total_time:.3f}s)"
    )
    print("-" * 80)
    print(" Single-Sample End-to-End Latency (Feature Extractor + XGBoost + TreeSHAP):")
    print(f"   • P50 Latency                       : {p50:.2f} ms")
    print(f"   • P90 Latency                       : {p90:.2f} ms")
    print(f"   • P95 Latency                       : {p95:.2f} ms")
    print(f"   • P99 Latency                       : {p99:.2f} ms")
    print(f"   • Mean Latency                      : {mean_lat:.2f} ms")
    print("=" * 80)

    target_met = p99 < 15.0
    print(f" Target Latency Criteria (P99 < 15.0ms) : [{'PASSED' if target_met else 'FAILED'}]")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark(1000)
