# TraceMind Synthetic Trace Dataset Specification

## 1. Overview & Objectives

This document formalizes the schema, generation dynamics, statistical distributions, and causal propagation rules governing synthetic datasets produced by **TraceSim** (`apps/simulator`).

TraceSim generates granular distributed trace telemetry without requiring live distributed clusters, enabling reproducible experiments in:
* Supervised in-flight workflow failure and latency prediction.
* TreeSHAP feature attribution and explainability.
* Unsupervised behavioral anomaly detection.
* Graph-based deterministic root-cause reasoning.
* Multi-objective workflow execution path optimization.

---

## 2. Simulated Workflow Topology

TraceSim executes an end-to-end distributed commerce/fulfillment pipeline across 7 distinct microservices:

```text
  [START]
     │
     ▼
┌──────────────┐
│ auth-service │ (authenticate_user)
└──────┬───────┘
     │
     ▼
┌──────────────────┐
│ customer-service │ (get_customer_profile)
└──────┬───────────┘
     │
     ├──────────────────────────┐ (Cache Miss: ~15%)
     │ (Cache Hit: ~85%)        ▼
     │                   ┌──────────────────┐
     │                   │ database-service │ (query_customer_db)
     │                   └────────┬─────────┘
     │                            │
     └────────────┬───────────────┘
                  ▼
         ┌──────────────────┐
         │ inventory-service│ (reserve_inventory)
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ pricing-service  │ (calculate_pricing)
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ payment-service  │ (authorize_payment)
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │  order-service   │ (create_order)
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────────┐
         │ notification-service │ (send_notification)
         └────────┬─────────────┘
                  │
                  ▼
                [END]
```

---

## 3. Dataset Schemas

### 3.1 `executions.jsonl` / `executions.parquet`
Represents the aggregated lifecycle record of an entire workflow instance.

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique deterministic identifier (e.g. `exec_42_000120`). |
| `workflow_definition_id` | `string` | Workflow topology ID (`order_fulfillment`). |
| `started_at` | `datetime` (UTC) | Workflow initiation timestamp. |
| `completed_at` | `datetime` (UTC) | Workflow terminal timestamp. |
| `status` | `string` | `COMPLETED` or `FAILED`. |
| `total_latency_ms` | `float` | Aggregate workflow execution duration in milliseconds. |
| `retry_count` | `int` | Total retry attempts across all invoked services. |
| `error_count` | `int` | Number of service-level errors encountered. |
| `failure_reason` | `string?` | Root error description if execution terminated in failure. |
| `metadata` | `json` | Execution metadata including correlation ID and sequence index. |

---

### 3.2 `events.jsonl` / `events.parquet`
Granular span-level lifecycle events emitted throughout workflow execution.

| Field | Type | Description |
|---|---|---|
| `event_id` | `string` | Unique event ID (`evt_...`). |
| `execution_id` | `string` | Associated parent execution run ID. |
| `workflow_id` | `string` | Workflow definition identifier. |
| `timestamp` | `datetime` (UTC) | Exact emission timestamp. |
| `service` | `string` | Executing service (e.g. `payment-service`). |
| `operation` | `string` | Specific operation executed (e.g. `authorize_payment`). |
| `event_type` | `string` | Classification: `WORKFLOW_STARTED`, `SERVICE_STARTED`, `SERVICE_COMPLETED`, `SERVICE_FAILED`, `SERVICE_TIMEOUT`, `RETRY_STARTED`, `RETRY_COMPLETED`, `CACHE_HIT`, `CACHE_MISS`, `DATABASE_QUERY`, `WORKFLOW_COMPLETED`, `WORKFLOW_FAILED`. |
| `status` | `string` | `SUCCESS`, `FAILURE`, `TIMEOUT`, `RETRY`. |
| `latency_ms` | `float` | Duration of the operation or step in milliseconds. |
| `parent_event_id` | `string?` | Parent trace span ID enabling trace graph reconstruction. |
| `correlation_id` | `string` | Distributed trace correlation identifier. |
| `metadata` | `json` | Detailed context (e.g. retry attempt index, error details). |

---

### 3.3 `incidents.jsonl` / `incidents.parquet`
Ground-truth causal incident records injected during the simulation.

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique incident ID (`inc_...`). |
| `scenario_type` | `string` | Scenario classification (e.g. `DATABASE_LATENCY`, `PAYMENT_LATENCY_DEGRADATION`). |
| `severity` | `string` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| `started_at` | `datetime` (UTC) | Incident onset timestamp. |
| `ended_at` | `datetime` (UTC) | Incident recovery timestamp. |
| `affected_services` | `json (list)` | Direct and indirectly degraded microservices. |
| `ground_truth_root_cause` | `string` | True root cause narrative for ML and RCA evaluation. |
| `description` | `string` | Technical explanation of the failure mechanism. |
| `parameters` | `json` | Incident injection parameters (multipliers, failure rates). |

---

## 4. Statistical Models & Distributions

### 4.1 Latency Sampling
Microservice processing latency is sampled from a mean-adjusted **Log-Normal distribution**:
$$f(x) = \frac{1}{x \sigma \sqrt{2\pi}} \exp\left( -\frac{(\ln x - \mu)^2}{2\sigma^2} \right)$$
where $\mu = \ln(\text{mean}) - \frac{1}{2}\sigma^2$. This guarantees that the expected value $\mathbb{E}[X]$ exactly equals the configured nominal baseline while preserving the characteristic right-skewed heavy tail observed in production distributed systems.

### 4.2 Natural Spikes
To model unpredictable background host degradation (e.g., JVM garbage collection pauses, thread pool starvation, TCP retransmissions), each service invocation has a configurable spike probability (default 2%) that scales the latency by $3.5\times$.

### 4.3 Concurrency & Queue Modeling
When the instantaneous concurrent load on a service exceeds its configured `capacity`, a non-linear queue delay is added:
$$\Delta t_{\text{queue}} = \left( \frac{\text{in\_flight} - \text{capacity}}{\text{capacity}} \right) \cdot \text{baseline\_latency} \cdot 1.5$$

### 4.4 Exponential Retry Backoff with Full Jitter
Client retries follow exponential backoff with full jitter:
$$t_{\text{backoff}} = \text{base\_backoff} \cdot 2^{\text{attempt}} \cdot \text{Uniform}(0.5, 1.5)$$

---

## 5. Causal Graph Propagation

TraceSim does NOT independently randomize metrics; instead, it enforces explicit causal propagation:

```text
Database Degradation Incident
  │
  ├─► database-service latency increases 5.5x
  │
  ├─► Downstream dependencies (customer, inventory, payment) experience:
  │     • 2.2x increased processing latency
  │     • Increased timeout probability
  │
  ├─► Client services trigger retry loops
  │
  ├─► Retries increase concurrency load across services
  │
  └─► Workflow total latency exceeds acceptable SLAs, resulting in WORKFLOW_FAILED
```

---

## 6. Reproducibility & Determinism

When configured with a fixed seed (e.g., `--seed 42`), TraceSim guarantees bit-exact reproducibility:
* Two independent simulation runs with identical seed and workflow count generate identical numbers of executions, identical event sequences, identical timestamps, and matching statistical distributions.
