# Application Observability: OpenTelemetry, Prometheus & Grafana

## 1. Overview & Architecture

Milestone 11 equips TraceMind with a comprehensive observability subsystem that allows the platform to **observe its own operational telemetry** across distributed trace generation, asynchronous streaming workers, machine learning model inference, graph root cause analysis, multi-objective Pareto optimization, and conversational AI analyst turns.

```
                    +-------------------------------------------------------------+
                    |                      TraceMind Gateway                      |
                    |  - OpenTelemetry Trace Middleware (W3C traceparent / IDs)   |
                    |  - Structured Logging Enrichment (trace_id, span_id, HTTP)  |
                    |  - Prometheus Metrics Registry (tracemind_* counters/hists) |
                    +-------------------------------------------------------------+
                                     |                             |
                       HTTP /metrics |                             | Structured Logs
                                     v                             v
                     +-------------------------------+   +--------------------+
                     |      Prometheus Scraper       |   |  Standard Output / |
                     |      (Port 9090 / 15s pull)   |   |  Vector Aggregator |
                     +-------------------------------+   +--------------------+
                                     |
                                     v
                     +-------------------------------+
                     |       Grafana Dashboard       |
                     |  - API Latencies (P50..P99)   |
                     |  - ML Inference & TreeSHAP    |
                     |  - Anomaly & RCA Distributions|
                     |  - Pareto Optimizer Stats     |
                     |  - AI Grounding & Safety      |
                     |  - Kafka Ingestion Throughput |
                     +-------------------------------+
```

---

## 2. OpenTelemetry Distributed Tracing & W3C Standards

### 2.1 Trace Context Protocol
TraceMind strictly implements the **W3C Trace Context Specification** (`traceparent` header):

$$\text{traceparent} = \text{version}-\text{trace\_id}-\text{parent\_span\_id}-\text{trace\_flags}$$

* **`version`**: `00` (Current W3C standard version).
* **`trace_id`**: 128-bit integer rendered as 32 lowercase hexadecimal characters (e.g., `4bf92f3577b34da6a3ce929d0e0e4736`).
* **`parent_span_id`**: 64-bit integer rendered as 16 lowercase hexadecimal characters (e.g., `00f067aa0ba902b7`).
* **`trace_flags`**: `01` (Recorded/Sampled) or `00` (Unsampled).

### 2.2 Response Headers & Correlation Propagation
Every HTTP response issued by TraceMind includes:
* `traceparent`: Full standard W3C header.
* `X-Trace-Id`: Direct 32-character hexadecimal correlation trace identifier.
* `X-Span-Id`: Direct 16-character hexadecimal span identifier.

### 2.3 Structlog Context Binding
The `TracingAndMetricsMiddleware` automatically binds `trace_id` and `span_id` to `structlog.contextvars`. Additionally, `add_opentelemetry_context` processor dynamically inspects active spans, ensuring 100% of logs generated anywhere within the backend include trace correlation fields.

---

## 3. Prometheus Metric Catalog & Low-Cardinality Rules

To prevent metric cardinality explosion in production time-series databases, all route parameters, trace identifiers, and user query strings are strictly normalized before label assignment:

| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `tracemind_http_requests_total` | Counter | `method`, `endpoint`, `status_code` | Total HTTP requests processed by API gateway. |
| `tracemind_http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request latency in seconds across fine-grained buckets ($1\text{ms}$ to $10\text{s}$). |
| `tracemind_ml_inference_duration_seconds` | Histogram | `model_name`, `task` | Execution duration for XGBoost, TreeSHAP, and regressor inference. |
| `tracemind_ml_predictions_total` | Counter | `model_name`, `risk_level` | Total in-flight risk predictions generated. |
| `tracemind_anomalies_detected_total` | Counter | `detector_type`, `severity` | Total anomalies discovered by unsupervised and heuristic detectors. |
| `tracemind_root_cause_diagnoses_total` | Counter | `category`, `culprit_service` | Total causal back-traversals and culprit diagnoses completed. |
| `tracemind_workflow_optimizations_total` | Counter | `optimization_type`, `workflow_id` | Total multi-objective Pareto routing recommendations computed. |
| `tracemind_analyst_queries_total` | Counter | `provider`, `status` | Total conversational AI Analyst turns processed. |
| `tracemind_analyst_grounding_score` | Gauge | `provider` | Moving average grounding compliance score ($0.0$ to $1.0$). |
| `tracemind_kafka_messages_ingested_total` | Counter | `topic` | Total raw trace events ingested from Kafka event streams. |
| `tracemind_database_connections_active` | Gauge | — | Active asyncpg connections held in connection pool. |

---

## 4. Fail-Open Architecture & Resilience

All telemetry hooks, OpenTelemetry spans, and Prometheus metric records are wrapped in fail-open handlers. Under zero circumstances will a logging, metric recording, or tracing failure propagate as an HTTP 500 error or interrupt distributed workflow evaluation.

---

## 5. Grafana Monitoring Stack

The platform provisions automated Prometheus scraping and Grafana dashboards via Docker Compose:

* **Prometheus Server**: Scrapes `http://api:8000/metrics` every 15 seconds.
* **Grafana Web UI**: Accessible on port `3000` with pre-configured dashboard JSON `tracemind_observability_dashboard.json`:
  1. **HTTP Request Rate & Status Distribution**: Real-time throughput by HTTP status code (2xx, 4xx, 5xx).
  2. **Latency Percentiles**: P50, P95, and P99 latency time series.
  3. **ML Inference Throughput & Durations**: XGBoost and TreeSHAP latency tracking.
  4. **Anomaly Detections by Type**: Latency Spikes, Error Cascades, Path Deviations, Isolation Forest.
  5. **Root Cause Analysis Incidents**: Breakdown of culprit microservices and failure categories.
  6. **3D Pareto Optimizer Throughput**: Multi-objective routing execution rate.
  7. **AI Analyst Grounding Gauge**: Live grounding compliance score ($> 95\%$ green).
  8. **Kafka Ingestion Lag & Stream Rate**: Throughput of background streaming ingestor.

---

## 6. Performance & Latency Overhead Benchmark

Measured via `benchmarks/benchmark_observability_overhead.py` over 1,000 requests:

| Percentile | Baseline Latency | Instrumented Latency | Overhead Delta ($\Delta$) | Quality Gate Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P50** | $0.001\text{ ms}$ | $0.062\text{ ms}$ | $+0.061\text{ ms}$ | — | **PASS** |
| **P90** | $0.001\text{ ms}$ | $0.108\text{ ms}$ | $+0.107\text{ ms}$ | — | **PASS** |
| **P95** | $0.001\text{ ms}$ | $0.139\text{ ms}$ | $+0.138\text{ ms}$ | — | **PASS** |
| **P99** | $0.001\text{ ms}$ | $0.246\text{ ms}$ | **$+0.245\text{ ms}$** | $< 0.500\text{ ms}$ | **PASS** |
| **Mean** | $0.001\text{ ms}$ | $0.089\text{ ms}$ | **$+0.088\text{ ms}$** | $< 0.200\text{ ms}$ | **PASS** |
