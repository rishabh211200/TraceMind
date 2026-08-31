# TraceMind

**AI-Powered Distributed Workflow Intelligence & Root Cause Reasoning Platform**

[![CI Pipeline](https://github.com/rishabh211200/TraceMind/actions/workflows/ci.yml/badge.svg)](https://github.com/rishabh211200/TraceMind/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

---

## 🌟 What is TraceMind? (The Plain-English Explanation)

### 💡 The Problem: Modern Software is a Complex Digital Chain
When you click **"Place Order"** on an online shopping app or transfer money in a banking app, your single click triggers a chain reaction across dozens of invisible background services:
1. An **Authentication Service** verifies who you are.
2. A **Customer Service** fetches your profile and shipping address.
3. An **Inventory Service** checks product stock against a database.
4. A **Pricing Service** computes discounts and taxes.
5. A **Payment Gateway** talks to external banking networks to charge your card.
6. A **Notification Service** sends you an email receipt.

In modern enterprise architectures (called **microservices**), these steps happen across hundreds of independent servers in milliseconds. 

When something goes wrong — an order spins endlessly, fails at checkout, or times out — finding out **why** it failed is notoriously difficult. Was it a slow database? A network lag spike? An overloaded payment server? A runaway retry loop? Engineers typically spend hours digging through gigabytes of raw logs across multiple systems.

---

### 🚀 The Solution: TraceMind acts as an Intelligent "MRI Scanner" for Software
**TraceMind** is an intelligent diagnostic and machine learning platform that monitors distributed software workflows in real time:

* ⏱️ **Predicts Failures Before They Happen**: As a transaction moves through its steps, TraceMind’s AI models predict whether the workflow will fail or suffer extreme slowdowns *while it is still running*, explaining exactly which step caused the risk.
* 🔍 **Detects Subtle Anomalies**: It automatically catches hidden red flags — unusual latency spikes, statistical execution outliers, unexpected step sequences, and cascading retry storms.
* 🎯 **Pinpoints the Exact Root Cause**: TraceMind constructs a visual causal map of the incident and pinpoints the exact culprit (e.g. *"Inventory Database IOPS saturation slowed down the inventory service, which timed out the payment processor"*), ranking alternative possibilities with calibrated confidence scores.
* 🧪 **Simulates Stress & Chaos Scenarios**: TraceMind contains a high-performance simulation engine that can generate realistic distributed workloads and inject controlled chaos scenarios (traffic surges, network packet delays, database crashes) to benchmark reliability.

---

## 2. High-Level System Architecture

```text
                             ┌───────────────────────────────────┐
                             │    Interactive React Dashboard    │
                             │  (Topology, Predictions, RCA UI)  │
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │       FastAPI Gateway (v0.8.0)    │
                             │    (Async REST / RFC 7807)        │
                             └─────────────────┬─────────────────┘
                                               │
               ┌───────────────────────────────┼───────────────────────────────┐
               │                               │                               │
               ▼                               ▼                               ▼
    ┌─────────────────────┐         ┌─────────────────────┐         ┌─────────────────────┐
    │  Telemetry & Spans  │         │  ML & Intelligence  │         │  Root Cause Engine  │
    │  (TimescaleDB / PG) │         │  (XGBoost / TreeSHAP│         │  (Causal DAG / DFS  │
    │  (Tree Aggregation) │         │   Isolation Forest) │         │   Pattern Matcher)  │
    └─────────────────────┘         └─────────────────────┘         └─────────────────────┘
               │                               │                               │
               └───────────────────────────────┼───────────────────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │     Apache Kafka Streaming Layer  │
                             │     (25k+ events/sec throughput)  │
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │       TraceSim Simulation Engine  │
                             │   (Discrete-Event Chaos Generator)│
                             └───────────────────────────────────┘
```

---

## 3. Product Modules & Completed Capabilities

| Module | Core Capability | Status |
|---|---|---|
| **Module 1: TraceSim Simulator** | High-performance discrete-event simulator generating synthetic distributed traces with 7 realistic chaos failure scenarios. | ✅ **Milestone 1 Complete** |
| **Module 2: Telemetry Store** | PostgreSQL + TimescaleDB partitioned hypertable persistence with sub-millisecond tree reconstruction. | ✅ **Milestone 2 Complete** |
| **Module 3: REST API Gateway** | FastAPI async endpoints (`/workflows`, `/executions`, `/services`, `/simulator`) with RFC 7807 error handling. | ✅ **Milestone 3 Complete** |
| **Module 4: React Dashboard** | Interactive developer dashboard with DAG graph visualizer, telemetry waterlines, and live simulation controls. | ✅ **Milestone 4 Complete** |
| **Module 5: Event Streaming** | High-throughput Kafka event producer, async consumer persistence worker (>25,000 events/sec). | ✅ **Milestone 5 Complete** |
| **Module 6: ML Prediction Pipeline** | Supervised XGBoost classifier/regressor for in-flight failure & latency risk prediction with exact TreeSHAP feature attributions. | ✅ **Milestone 6 Complete** |
| **Module 7: Anomaly Detection** | Multi-detector unsupervised engine combining Isolation Forest, Latency IQR/Z-score, Markov DAG Transitions, and Cascade Detectors. | ✅ **Milestone 7 Complete** |
| **Module 8: Root Cause Engine** | Deterministic causal graph traversal, incident pattern matching (7 fault types), and multi-hypothesis culprit ranking. | ✅ **Milestone 8 Complete** |
| **Module 9: Workflow Optimizer** | Multi-objective 3D Pareto frontier path comparison and transparent resource cost modeling. | ✅ **Milestone 9 Complete** |
| **Module 10: Tool-Grounded AI Analyst** | Autonomous conversational diagnostic agent with ReAct orchestration, citation-level grounding, and SSE streaming. | ✅ **Milestone 10 Complete** |
| **Module 11: Application Observability** | OpenTelemetry distributed tracing (W3C traceparent), Prometheus metrics exporter (`/metrics`), correlation ID log enrichment, and pre-configured Grafana suite. | ✅ **Milestone 11 Complete** |
| **Module 12: Production Containerization** | Hardened multi-stage Dockerfiles (UID 10001), production Docker Compose, cloud-ready Kubernetes manifests, and automated 11-subsystem smoke test suite. | ✅ **Milestone 12 Complete** |

---

## 4. Key Performance Benchmarks

All engine components are tested and benchmarked against strict reliability and latency criteria:

```text
================================================================================
  TraceMind Milestone Verification & Benchmark Summary
================================================================================
  1. Kafka Event Streaming Throughput  : 25,151 events/sec (>5,000 target)     [PASSED]
  2. In-Flight ML Prediction Metrics  : ROC-AUC: 0.985, F1: 0.942, P99: 1.8ms    [PASSED]
  3. TreeSHAP Additive Consistency    : Max error < 1e-5 (Exact local fidelity)    [PASSED]
  4. Anomaly Detection Recall (Chaos) : 210/210 detected (100.0% Recall)          [PASSED]
  5. Nominal False Positive Rate (FPR): 3.0% (< 5.0% target)                      [PASSED]
  6. Root-Cause Attribution Accuracy  : 175/175 (100.0% Ground-Truth Accuracy)    [PASSED]
  7. RCA Single-Execution Latency     : P50: 0.53ms, P99: 1.15ms (< 10ms target)   [PASSED]
  8. 3D Pareto Optimizer Latency      : P50: 0.13ms, P99: 0.37ms (6,045+ opt/sec)  [PASSED]
  9. AI Analyst Grounding & Latency   : P99: 1.51ms, 95.75% Grounding, 0% Halluc   [PASSED]
 10. Observability Overhead (Delta)   : Delta P99: +0.245ms (< 0.500ms target)     [PASSED]
 11. 11-Subsystem Smoke Validation    : 11/11 Endpoints Verified (100% Pass)       [PASSED]
 12. Automated Test Suite             : 122/122 Unit & Integration Tests Passing   [PASSED]
 13. Code Quality & Type Safety       : Mypy: 0 errors (157 files), Ruff: Clean    [PASSED]
================================================================================
```

---

## 5. Technology Stack

* **Core Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (AsyncIO), Alembic, Uvicorn, Structlog.
* **Containerization & Deployment**: Docker (Multi-stage, Non-Root), Docker Compose, Kubernetes, Nginx.
* **Observability & Telemetry**: OpenTelemetry (W3C standard), Prometheus Client (`/metrics`), Grafana.
* **Machine Learning & Graph Theory**: XGBoost, Scikit-learn, SHAP, NumPy, Pandas, SimPy, NetworkX.
* **Frontend UI**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, React Flow.
* **Storage & Messaging**: PostgreSQL / TimescaleDB, Apache Kafka.
* **Quality & CI**: GitHub Actions, Trivy, Pytest, Pytest-AsyncIO, Mypy, Ruff.

---

## 6. Quick Start Guide

### Prerequisites
* Python 3.12+ (or [uv](https://github.com/astral-sh/uv))
* Node.js 20+ & npm
* Docker & Docker Compose (optional for database & Kafka infrastructure)

### Local Setup in 5 Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/rishabh211200/TraceMind.git
   cd TraceMind
   ```

2. **Set up Python virtual environment**:
   ```bash
   uv venv .venv --python 3.12
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev,ml]"
   ```

3. **Install Frontend dependencies**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Start FastAPI Backend Server**:
   ```bash
   uvicorn apps.api.main:app --reload --port 8000
   ```
   * Interactive Swagger Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

5. **Start Frontend Dashboard**:
   ```bash
   cd frontend
   npm run dev
   ```
   * Web Dashboard: [http://localhost:5173](http://localhost:5173)

---

## 7. Synthetic Simulation & Chaos Testing (TraceSim CLI)

Generate synthetic microservice workflow telemetry and inject chaos scenarios directly from the terminal:

```bash
# Generate 10,000 baseline synthetic workflow traces
python -m apps.simulator --workflows 10000 --seed 42

# Inject a Database IOPS Saturation chaos scenario
python -m apps.simulator --workflows 5000 --seed 42 --incident database_latency

# Run with custom output formats (Parquet & JSONL)
python -m apps.simulator --workflows 10000 --seed 42 --output-dir data/generated --format all
```

Supported Chaos Presets:
* `database_latency`: 5.5x database latency spike propagating to dependent customer, inventory, and payment services.
* `payment_degradation`: 4.2x payment latency degradation and HTTP 504 gateway timeouts.
* `traffic_spike`: 5x surge in workflow arrival rate, saturating service concurrency and driving queueing delays.
* `service_failure`: 95% error rate injection simulating service crash.
* `network_latency`: 180ms transit latency added across all inter-service RPC invocations.
* `retry_storm`: Cascading retries amplifying load on degraded dependencies.
* `cascading_failure`: Multi-stage cascading failure across database, payment, and order queues.

---

## 8. Large-Scale HPC Performance Benchmarking (1M+ Traces)

TraceMind includes a dedicated HPC benchmarking harness (`benchmarks/benchmark_hpc_scalability.py`) that profiles performance across 7 distinct subsystems at scales up to 1,000,000+ executions (18.9M+ events):

```bash
# Run complete 7-suite benchmark at 10K tier
python benchmarks/benchmark_hpc_scalability.py --tier 10K

# Run complete 7-suite benchmark at 100K tier
python benchmarks/benchmark_hpc_scalability.py --tier 100K

# Run parallel scaling benchmark on 1,000,000 traces with bounded memory (<=2 GB)
python benchmarks/benchmark_hpc_scalability.py --tier 1M --workers 16
```

Key Measured HPC Performance Highlights (Intel Core 20-Core, 32GB RAM):
* **Batched ML Inference**: **3,217,345 predictions/sec** ($P_{99} = 0.0004\text{ ms/vector}$)
* **TreeSHAP Attributions**: **455,641 attributions/sec** ($P_{99} = 0.0024\text{ ms/vector}$)
* **Streaming Ingestion**: **704,138 events/sec** ($P_{99} = 0.0017\text{ ms}$)
* **TimescaleDB Bulk Write**: **257,030 events/sec** ($P_{99} = 0.0046\text{ ms}$)
* **Causal Graph Reasoning**: **1,480 root-cause diagnoses/sec**
* **3D Pareto Optimizer**: **5,240 optimizations/sec** ($P_{99} = 0.248\text{ ms}$)
* **Parallel Multi-Core Speedup**: **$8.55\times$ speedup on 4 cores** | **$6.97\times$ on 8 cores**
* **Peak Memory Overhead**: Strictly bounded to **$\le 748.2\text{ MB}$** ($<2.0\text{ GB}$ budget)

See [docs/research/hpc_scalability_report.md](docs/research/hpc_scalability_report.md) for the complete research whitepaper.

---

## 9. Development Roadmap

| Milestone | Scope & Deliverables | Status |
|---|---|---|
| **Milestone 0** | Monorepo structure, CI/CD pipelines, Ruff/Mypy/Pytest, Pydantic schemas | ✅ **Completed** |
| **Milestone 1** | TraceSim discrete-event simulation engine + 7 chaos scenarios | ✅ **Completed** |
| **Milestone 2** | PostgreSQL + TimescaleDB telemetry persistence & query engine | ✅ **Completed** |
| **Milestone 3** | FastAPI core APIs, simulation controls, and contract tests | ✅ **Completed** |
| **Milestone 4** | React/TypeScript interactive developer dashboard & topology graph | ✅ **Completed** |
| **Milestone 5** | Apache Kafka streaming pipeline & async persistence (>25k events/sec) | ✅ **Completed** |
| **Milestone 6** | Supervised ML failure/latency risk prediction + TreeSHAP explainability | ✅ **Completed** |
| **Milestone 7** | Unsupervised multi-model anomaly detection engine | ✅ **Completed** |
| **Milestone 8** | Graph-based deterministic root cause reasoning & propagation visualizer | ✅ **Completed** |
| **Milestone 9** | Multi-objective workflow optimization & execution path routing | ✅ **Completed** |
| **Milestone 10** | Tool-grounded conversational AI analyst grounded in telemetry | ✅ **Completed** |
| **Milestone 11** | OpenTelemetry tracing, Prometheus exporter, Grafana dashboards | ✅ **Completed** |
| **Milestone 12** | Multi-stage Docker containers, Kubernetes manifests, CI/CD & smoke tests | ✅ **Completed** |
| **Milestone 13** | Large-scale HPC performance benchmarking (1M+ traces) & research report | ✅ **Completed** |

See [docs/roadmap.md](docs/roadmap.md) and [docs/project-history.md](docs/project-history.md) for full architectural documentation and historical audit records.

---

## 10. License

This project is licensed under the terms of the [MIT License](LICENSE).