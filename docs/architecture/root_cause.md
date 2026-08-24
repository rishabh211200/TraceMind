# Root Cause Engine & Graph-Based Deterministic Reasoning (Milestone 8)

## 1. Overview & Architecture

The **Root Cause Engine (RCA)** in TraceMind implements deterministic, graph-theoretic causal analysis across distributed workflow execution graphs. While Milestone 6 predicts failure risks and Milestone 7 detects multi-detector anomalies (outliers, latency spikes, path deviations, retry storms), Milestone 8 answers:
1. **What is the root cause?** (e.g. Database IOPS Saturation, Hard Service Crash, Cascading Retry Storm, Network Transit Delay).
2. **Which service is the root culprit?** (e.g. `inventory-db`, `payment-service`, `auth-service`).
3. **What is the causal propagation graph path?** (e.g. `inventory-db` $\to$ `inventory-service` $\to$ `order-service` $\to$ `api-gateway`).
4. **How confident is the diagnosis?** (Calibrated $[0.0, 1.0]$ confidence score).
5. **What is the quantitative technical evidence?** (Exact timestamps, latencies vs baselines, retry counts, TreeSHAP attributions).

```
 +---------------------------------------------------------------------------------------+
 |                                  Execution Inputs                                     |
 +---------------------------------------------------------------------------------------+
    |                                   |                                   |
    v                                   v                                   v
 +----------------------+    +----------------------+    +----------------------+
 | M1 Trace Spans       |    | M6 TreeSHAP          |    | M7 Detected          |
 | Chronological events |    | Feature attributions |    | Anomalies & Evidence |
 +----------------------+    +----------------------+    +----------------------+
    |                                   |                                   |
    +-----------------------------------+-----------------------------------+
                                        |
                                        v
 +---------------------------------------------------------------------------------------+
 |                     Milestone 8: Root Cause Reasoning Engine                          |
 +---------------------------------------------------------------------------------------+
 |  1. Causal Temporal DAG Construction (V: Spans/Anomalies, E: Invocations/Dataflow)   |
 |  2. Upstream Back-Traversal from Terminal Symptom to Earliest Point of Degradation    |
 |  3. Multi-Criteria Confidence Scoring (Earliest timestamp, Depth, Severity, SHAP)     |
 |  4. Incident Pattern Signature Matching (DB Saturation, Crash, Retry Storm, Transit) |
 |  5. Multi-Hypothesis Generation & Ranking (Primary Culprit + Alternative Hypotheses)  |
 +---------------------------------------------------------------------------------------+
                                        |
    +-----------------------------------+-----------------------------------+
    |                                   |                                   |
    v                                   v                                   v
 +----------------------+    +----------------------+    +----------------------+
 | PostgreSQL Database  |    | FastAPI REST APIs    |    | React RCA Dashboard  |
 | workflow_root_causes |    | /api/v1/root-cause   |    | Causal Graph & Modal |
 +----------------------+    +----------------------+    +----------------------+
```

---

## 2. Mathematical Formulations & Algorithms

### A. Temporal Causal Graph Construction
A directed graph $G = (V, E)$ is built from chronological trace events:
$$v = \langle \text{service}, \text{operation}, \text{timestamp}, \text{latency\_ms}, \text{status}, \text{anomalies}, \text{shap\_attribution} \rangle$$
Edges $E = \{(u \to v)\}$ represent temporal caller-to-callee dependencies and parent-child span transitions.

### B. Upstream Back-Traversal
From symptom nodes $S_{\text{fail}} \subseteq V$ (failing operations or extreme latency bottlenecks $\ge 1000\text{ms}$), the engine traverses backwards along reverse edges $\text{pred}(v)$:
$$\Pi = \langle s_0, s_1, \dots, s_k \rangle$$
Where $s_0$ represents the origin root culprit component and $s_k$ is the terminal symptom gateway.

### C. Multi-Criteria Culprit Scoring
For each candidate service $s \in V$:
1. **Hard Failure**: Base score $0.95 + 0.04 \cdot \Phi_{\text{latency}} + 0.01 \cdot \Phi_{\text{time}}$
2. **Multi-Retry Storm ($\ge 2$ retries)**: Base score $0.92 + 0.06 \cdot \Phi_{\text{latency}} + 0.02 \cdot \Phi_{\text{time}}$
3. **Severe Latency Degradation ($\Phi_{\text{latency}} \ge 0.40$)**: Base score $0.75 + 0.20 \cdot \Phi_{\text{latency}} + 0.05 \cdot \Phi_{\text{time}}$
4. **Statistical Outlier**: $0.50 \cdot \Phi_{\text{latency}} + 0.30 \cdot \text{Score}_{\text{anomaly}} + 0.10 \cdot \Phi_{\text{shap}} + 0.10 \cdot \Phi_{\text{time}}$

Where:
$$\Phi_{\text{latency}}(s) = \min\left(1.0, \frac{\text{latency}(s) / \text{baseline}(s) - 1.0}{2.0}\right)$$
$$\Phi_{\text{time}}(s) = \exp\left(-0.6 \cdot \frac{t_{\text{first}}(s) - t_{\text{min}}}{\Delta t_{\text{total}}}\right)$$

### D. Canonical Incident Patterns
1. **`DATABASE_IOPS_SATURATION`**: Database component query latency exceeds baseline causing upstream caller timeouts.
2. **`SERVICE_CRASH`**: Fatal service execution failure with HTTP 500 error.
3. **`CASCADING_RETRY_STORM`**: Client retry bursts ($\ge 3$ retries) exhausting thread pools.
4. **`NETWORK_TRANSIT_DELAY`**: Cross-service packet loss adding +180ms transit delays.
5. **`FLASH_TRAFFIC_OVERLOAD`**: Entry gateway arrival surge causing broad concurrent queueing lag.
6. **`DEPENDENCY_TIMEOUT`**: Callee response latency breaches SLA budget.

---

## 3. Database Persistence Schema (`workflow_root_causes`)

```sql
CREATE TABLE workflow_root_causes (
    id VARCHAR(64) PRIMARY KEY,
    execution_id VARCHAR(64) NOT NULL REFERENCES workflow_executions(id),
    workflow_definition_id VARCHAR(64) NOT NULL DEFAULT 'order_fulfillment',
    culprit_service VARCHAR(64) NOT NULL,
    incident_category VARCHAR(64) NOT NULL,
    confidence FLOAT NOT NULL,
    causal_path JSON NOT NULL DEFAULT '[]',
    supporting_evidence JSON NOT NULL DEFAULT '[]',
    alternative_hypotheses JSON NOT NULL DEFAULT '[]',
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_workflow_root_causes_execution_id ON workflow_root_causes (execution_id);
CREATE INDEX ix_workflow_root_causes_culprit_service ON workflow_root_causes (culprit_service);
CREATE INDEX ix_workflow_root_causes_incident_category ON workflow_root_causes (incident_category);
```

---

## 4. REST API Reference (`/api/v1/root-cause`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/root-cause/analyze` | On-demand graph reasoning & optional DB persistence |
| `GET` | `/api/v1/root-cause/executions/{execution_id}` | List historical RCA reports for an execution |
| `GET` | `/api/v1/root-cause` | Paginated search (`workflow_id`, `culprit`, `category`, `confidence`) |
| `GET` | `/api/v1/root-cause/stats` | Aggregate summary statistics (by category, top culprits, mean confidence) |
| `GET` | `/api/v1/root-cause/{id}` | Single RCA report details |

---

## 5. Benchmark Performance

```text
================================================================================
       TraceMind Milestone 8 Deterministic Root Cause Engine Benchmark       
================================================================================
1. Validating Ground-Truth Root-Cause Attribution Across 7 Chaos Presets:
--------------------------------------------------------------------------------
  [1/7] Payment Latency Spike (4.2x)         : 25/25 (100.0% Accuracy) [PASSED]
  [2/7] Database IOPS Saturation (5.5x)      : 25/25 (100.0% Accuracy) [PASSED]
  [3/7] Service Crash (95% error)            : 25/25 (100.0% Accuracy) [PASSED]
  [4/7] Flash Traffic Arrival Surge (5x)     : 25/25 (100.0% Accuracy) [PASSED]
  [5/7] Transit Packet Loss (+180ms)         : 25/25 (100.0% Accuracy) [PASSED]
  [6/7] Cascading Client Retry Storm         : 25/25 (100.0% Accuracy) [PASSED]
  [7/7] Cascading Multi-Service Outage       : 25/25 (100.0% Accuracy) [PASSED]
--------------------------------------------------------------------------------
  Overall Root-Cause Attribution Accuracy : 175/175 (100.0%) [Target >= 95.0%]

2. Benchmarking Single-Execution Graph Reasoning Latency (1,000 Iterations):
--------------------------------------------------------------------------------
  Benchmark Executions Processed      : 1,000 runs in 0.568s
  Throughput                          : 1,760.3 diagnoses/sec
  P50 Diagnosis Latency               : 0.53 ms
  P90 Diagnosis Latency               : 0.69 ms
  P95 Diagnosis Latency               : 0.84 ms
  P99 Diagnosis Latency               : 1.15 ms [Target < 10.0ms]
  Max Diagnosis Latency               : 1.78 ms
  Mean Diagnosis Latency              : 0.57 ms
================================================================================
```
