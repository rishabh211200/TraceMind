# TraceMind Architecture Overview

## 1. System Philosophy

TraceMind is designed to bridge distributed tracing, machine learning, and automated operational intelligence. Modern microservice workflows are complex non-linear graphs characterized by variable latencies, transient network failures, retry storms, and cascading dependency degradation.

TraceMind provides a unified pipeline that:
1. **Generates or Ingests Traces**: Simulates multi-service workflows with configurable baselines and chaos scenarios.
2. **Structures Graph Topologies**: Mines workflow graphs, node frequencies, and transition probabilities.
3. **Infers Operational Risk**: Applies ML models (XGBoost, Random Forest, Isolation Forest) to flag anomalies and predict workflow failures before completion.
4. **Performs Causal Reasoning**: Discovers root causes deterministically before using an LLM.
5. **Recommends Optimal Strategies**: Suggests routing, fallback, and retry strategies.
6. **Enables Conversational Intelligence**: Empowers engineers through tool-calling AI analysts without data hallucination.

---

## 2. High-Level Data Flow

```text
 ┌─────────────────┐
 │ TraceSim Engine │
 └────────┬────────┘
          │ (Trace Events)
          ▼
 ┌─────────────────┐
 │  Kafka Bus      │  (Milestone 5+)
 └────────┬────────┘
          │
          ▼
 ┌─────────────────┐     ┌─────────────────────┐
 │ Trace Ingestor  ├────►│ PostgreSQL /        │
 └────────┬────────┘     │ TimescaleDB Storage │
          │              └──────────┬──────────┘
          ▼                         │
 ┌─────────────────┐                │
 │ Feature Engine  │◄───────────────┘
 └────────┬────────┘
          │
     ┌────┴───────────────────────────┐
     ▼                                ▼
┌───────────────┐             ┌───────────────┐
│ ML Predictor  │             │ Anomaly Engine│
│ (Failure/Lag) │             │ (Outliers)    │
└───────┬───────┘             └───────┬───────┘
        │                             │
        └──────────────┬──────────────┘
                       ▼
          ┌───────────────────────────┐
          │  Root Cause Reasoner      │
          │  (Graph-Based Deduction)  │
          └────────────┬──────────────┘
                       │
                       ▼
          ┌───────────────────────────┐
          │ AI Analyst (Tool-Grounded)│
          └────────────┬──────────────┘
                       │
                       ▼
          ┌───────────────────────────┐
          │ React Interactive Dashboard│
          └───────────────────────────┘
```

---

## 3. Detailed Component Breakdown

### 3.1 TraceSim Simulator (`apps/simulator`, `packages/workflow`)
* Built on discrete-event simulation (`SimPy`).
* Manages simulated generic services: `auth-service`, `customer-service`, `inventory-service`, `pricing-service`, `payment-service`, `order-service`, `notification-service`.
* Each service specifies:
  - Latency distributions (Log-Normal, Gamma, Gaussian).
  - Concurrency capacity and queue limits.
  - Failure probabilities and retry budgets.
  - Client timeout configurations.
* Supports reproducible generation using pseudo-random seeds.

### 3.2 Trace Store & Data Layer (`packages/database`, `packages/domain`)
* Powered by PostgreSQL with TimescaleDB hypertable extensions for time-series event partitioning.
* Tables:
  - `workflow_definitions`: Topology node/edge metadata.
  - `workflow_executions`: Aggregate metrics per execution run.
  - `trace_events`: Granular span-level lifecycle events.
  - `incidents`: Ground-truth incident records.
  - `predictions`: Model outputs and SHAP feature attributions.
  - `anomalies`: Flagged statistical anomalies.
* Indexed on `execution_id`, `workflow_id`, `timestamp`, `service`, and `event_type`.

### 3.3 Event Streaming & Ingestion Engine (`packages/events`, `apps/worker`)
* Powered by Apache Kafka in KRaft mode with asyncio-native `aiokafka` producers and consumers.
* Topics:
  - `tracemind.events.raw`: Partitioned causally by `execution_id` to guarantee FIFO span ordering.
  - `tracemind.events.anomalies`: Stream of flagged statistical and ML-detected anomalies.
* Streaming Ingestion Worker (`apps/worker/stream_ingestor.py`):
  - Consumes from `tracemind.events.raw` using group `tracemind-ingestor`.
  - Buffers spans into micro-batches ($1,000$ events / $50\text{ms}$).
  - Executes single-pass multi-row bulk `insert(TraceEventModel)` into TimescaleDB with idempotent merge fallback.
  - Commits Kafka offsets strictly after database persistence succeeds.
* Dual-Mode Event Bus (`InMemoryEventBus`): Supports 100% hermetic CI/CD unit testing without requiring an external broker.

### 3.4 ML Engine (`apps/ml`)
* **Failure Prediction**: Binary classification problem targeting in-flight workflow success/failure using running features (elapsed time, completed step count, latency statistics, retry counts).
* **Latency Prediction**: Regression problem predicting total workflow completion time.
* **Explainability**: TreeSHAP values generated for every prediction to show the top contributing features and directional impact (+/- risk).
* **Tracking**: Experiment logging with MLflow.

### 3.4 Root Cause Engine (`packages/workflow`, `apps/api`)
* Evaluates dependency graphs against observed latency anomalies, error rate deltas, and retry spikes.
* Follows causal graph traversal: identifying the leaf service where degradation originated before cascading to downstream consumers.
* Computes deterministic confidence metrics and structured evidence prior to any AI synthesis.

### 3.5 AI Analyst (`apps/ai`)
* Uses provider-agnostic tool calling (OpenAI, Anthropic, Gemini, or local models).
* Safe, read-only tools:
  - `get_system_health()`
  - `get_workflow(workflow_id)`
  - `get_execution_trace(execution_id)`
  - `get_service_metrics(service_name)`
  - `get_recent_anomalies()`
  - `get_predictions(execution_id)`
  - `get_dependency_graph(workflow_id)`
  - `get_incidents()`
* Clear boundary between *Observed Facts*, *Model Predictions*, *Inferred Causes*, and *Recommendations*.

### 3.6 REST API Layer (`apps/api/`)
* Built with FastAPI and Pydantic v2.
* Conforms to RFC 7807 Problem Details for standardized, typed error responses.
* Core Routing Domains:
  - `/api/v1/workflows`: Workflow DAG definition registration, cycle validation, execution listings, and statistical aggregations.
  - `/api/v1/executions`: Execution search and history with multi-column filtering, span chronological stream, and recursive DAG tree reconstruction.
  - `/api/v1/simulator`: Scenario catalog, in-memory synthetic trace generation, and targeted causal chaos injection.
  - `/api/v1/services`: Microservice profile catalog, baseline updates, latency percentiles, and system dependency graph topology (`/topology`).
  - `/api/v1/incidents`: Ground-truth chaos incidents and affected execution trace listings.

### 3.7 Frontend Dashboard (`frontend/`)
* Built with React, TypeScript, Vite, and Tailwind CSS.
* Core views:
  - **Dashboard**: Real-time KPI summaries, active anomalies, workflows at risk.
  - **Workflow Explorer**: Interactive React Flow graph viewer showing service dependencies and traffic weights.
  - **Execution Trace Viewer**: Waterfall Gantt chart of trace spans.
  - **Prediction & SHAP View**: Risk scores and feature attribution charts.
  - **Root Cause Inspector**: Causal path highlight and evidence list.
  - **Chaos Simulator Console**: Parameter tuning and synthetic incident injection.
  - **AI Analyst Assistant**: Conversational assistant grounded with live tools.

---

## 4. Security & Safety

* No proprietary code or company data: 100% synthetic generation.
* Strict input validation via Pydantic models.
* No raw SQL or unrestricted DB access granted to LLMs.
* Environment-based credential and secret handling.
