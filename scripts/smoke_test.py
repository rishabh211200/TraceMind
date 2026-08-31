"""Production Smoke Test Suite: Validates all 11 TraceMind subsystems end-to-end.

Can be run against a running server (e.g. python scripts/smoke_test.py http://localhost:8000)
or directly in test pipelines.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def _make_request(
    base_url: str,
    endpoint: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | str, float]:
    """Execute standard HTTP request and measure latency."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start_time = time.perf_counter()

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            body = resp.read().decode("utf-8")
            status_code = resp.status
            try:
                parsed_json = json.loads(body)
                return status_code, parsed_json, elapsed_ms
            except Exception:
                return status_code, body, elapsed_ms
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        err_body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(err_body), elapsed_ms
        except Exception:
            return exc.code, err_body, elapsed_ms
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return 0, str(exc), elapsed_ms


def run_smoke_tests(base_url: str = "http://localhost:8000") -> bool:
    """Execute comprehensive 11-subsystem smoke test suite."""
    print("=" * 80)
    print(f"       TraceMind Production Smoke Test Suite — Target: {base_url}       ")
    print("=" * 80)

    test_cases = [
        # 1. API Health Probe
        (
            "1. System Health & Readiness Probe",
            "GET",
            "/api/v1/health",
            None,
            lambda status, body: (
                status == 200 and isinstance(body, dict) and body.get("status") == "healthy"
            ),
        ),
        # 2. Root API Metadata
        (
            "2. Root Metadata & OpenAPI Route",
            "GET",
            "/",
            None,
            lambda status, body: status == 200 and isinstance(body, dict) and "service" in body,
        ),
        # 3. Microservice Topology Graph
        (
            "3. Microservices Topology Graph",
            "GET",
            "/api/v1/services/topology",
            None,
            lambda status, body: status == 200 and isinstance(body, dict) and "nodes" in body,
        ),
        # 4. Workflow DAG Listing
        (
            "4. Workflow DAG Definition Registry",
            "GET",
            "/api/v1/workflows",
            None,
            lambda status, body: status == 200 and isinstance(body, list),
        ),
        # 5. Synthetic Trace Simulation Generator
        (
            "5. Deterministic TraceSim Generator",
            "POST",
            "/api/v1/simulator/generate",
            {
                "workflow_count": 5,
                "seed": 42,
                "inject_incidents": False,
                "persist_to_db": False,
            },
            lambda status, body: (
                status == 200 and isinstance(body, dict) and body.get("executions_generated") == 5
            ),
        ),
        # 6. In-Flight Failure & TreeSHAP Prediction
        (
            "6. In-Flight XGBoost & TreeSHAP Inference",
            "POST",
            "/api/v1/predictions/predict",
            {
                "execution_id": "exec_smoke_test_01",
                "workflow_definition_id": "order_fulfillment",
                "events": [
                    {
                        "event_id": "ev_01",
                        "execution_id": "exec_smoke_test_01",
                        "service": "auth-service",
                        "operation": "verify_token",
                        "event_type": "SPAN_START",
                        "status": "SUCCESS",
                        "latency_ms": 12.5,
                        "timestamp": "2026-08-29T12:00:00Z",
                    }
                ],
                "persist_to_db": False,
            },
            lambda status, body: (
                status == 200 and isinstance(body, dict) and "failure_probability" in body
            ),
        ),
        # 7. Unsupervised Anomaly Detection
        (
            "7. Unsupervised Outlier & Anomaly Detection",
            "POST",
            "/api/v1/anomalies/detect",
            {
                "execution_id": "exec_smoke_test_02",
                "workflow_definition_id": "order_fulfillment",
                "events": [
                    {
                        "event_id": "ev_02",
                        "execution_id": "exec_smoke_test_02",
                        "service": "payment-gateway",
                        "operation": "process_charge",
                        "event_type": "SPAN_START",
                        "status": "ERROR",
                        "latency_ms": 850.0,
                        "timestamp": "2026-08-29T12:00:00Z",
                    }
                ],
                "persist_to_db": False,
            },
            lambda status, body: status == 200 and isinstance(body, dict) and "anomalies" in body,
        ),
        # 8. Deterministic Causal Root Cause Diagnosis
        (
            "8. Causal Graph Root Cause Reasoning",
            "POST",
            "/api/v1/root-cause/analyze",
            {
                "execution_id": "exec_smoke_test_03",
                "workflow_definition_id": "order_fulfillment",
                "events": [
                    {
                        "event_id": "ev_03",
                        "execution_id": "exec_smoke_test_03",
                        "service": "inventory-db",
                        "operation": "query_stock",
                        "event_type": "SPAN_START",
                        "status": "ERROR",
                        "latency_ms": 1200.0,
                        "timestamp": "2026-08-29T12:00:00Z",
                    }
                ],
                "persist_to_db": False,
            },
            lambda status, body: (
                status == 200 and isinstance(body, dict) and "culprit_service" in body
            ),
        ),
        # 9. 3D Pareto Optimal Path Optimizer
        (
            "9. Multi-Objective 3D Pareto Optimizer",
            "POST",
            "/api/v1/optimizer/recommend",
            {
                "workflow_definition_id": "order_fulfillment",
                "latency_weight": 0.4,
                "cost_weight": 0.3,
                "reliability_weight": 0.3,
            },
            lambda status, body: (
                status == 200 and isinstance(body, dict) and "recommended_path" in body
            ),
        ),
        # 10. Tool-Grounded Conversational AI Analyst
        (
            "10. Tool-Grounded Conversational AI Analyst",
            "POST",
            "/api/v1/analyst/chat",
            {
                "query": "What is the health of the system topology?",
                "provider": "mock",
                "persist": False,
            },
            lambda status, body: status == 200 and isinstance(body, dict) and "content" in body,
        ),
        # 11. Prometheus Metrics Exposition
        (
            "11. Prometheus Metrics Exposition (/metrics)",
            "GET",
            "/metrics",
            None,
            lambda status, body: status == 200 and "tracemind_http_requests_total" in str(body),
        ),
    ]

    all_passed = True
    for name, method, endpoint, payload, validator in test_cases:
        status, body, latency = _make_request(base_url, endpoint, method, payload)
        passed = validator(status, body)

        status_str = "[PASS]" if passed else "[FAIL]"
        print(f"  {name:<48} : {status_str} (HTTP {status}, {latency:6.2f} ms)")
        if not passed:
            all_passed = False
            print(f"     --> Error details: {str(body)[:160]}")

    print("=" * 80)
    if all_passed:
        print("   >>> PRODUCTION SMOKE TEST SUITE PASSED ALL 11 SUB-SYSTEM GATES <<<   ")
    else:
        print("   >>> PRODUCTION SMOKE TEST SUITE FAILED ONE OR MORE GATES <<<   ")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    success = run_smoke_tests(target)
    sys.exit(0 if success else 1)
