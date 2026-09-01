# TraceMind

**AI-Powered Distributed Workflow Intelligence, Root Cause Reasoning & Autonomous Remediation Platform**

[![CI Pipeline](https://github.com/rishabh211200/TraceMind/actions/workflows/ci.yml/badge.svg)](https://github.com/rishabh211200/TraceMind/actions/workflows/ci.yml)
[![Tests: 162 Passing](https://img.shields.io/badge/tests-162%20passed-success.svg)](tests/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![TypeScript 5](https://img.shields.io/badge/typescript-5.x-blue.svg)](frontend/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy Strict](https://img.shields.io/badge/type%20checked-mypy%20strict-blue.svg)](http://mypy-lang.org/)

---

> 🚀 **Quick Interactive Demo (Zero Cloud Cost & Under 60 Seconds)**  
> Experience the complete TraceMind platform (M0–M15) locally or in GitHub Codespaces without any paid cloud dependencies or external API keys:  
> ```bash
> # 1. Start the single-port demo stack (Port 80 only)
> docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build
> 
> # 2. Seed deterministic chaos telemetry, trained ML models & 4 showcase scenarios
> docker compose -f docker-compose.demo.yml exec api python scripts/demo_bootstrap.py
> 
> # 3. Open dashboard at http://localhost (Admin: admin@tracemind.io / TraceMind#Admin2026!)
> ```
> * **Zero Outbound AI Calls**: Uses in-process `MockLLMClient` with deterministic regex/keyword tool resolution.  
> * **Zero External Actuation**: Uses `InMemoryRoutingActuator` with thread-safe state snapshots.  
> * Full step-by-step walkthrough & scenario storyboards: **[`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md)**

---

## 1. What is TraceMind? (The Plain-English Overview)

### 💡 The Problem: Distributed Microservices are Fragile Digital Chains
When you click **"Place Order"** in a modern e-commerce application or transfer funds in a banking app, your single click triggers an invisible chain reaction across dozens of independent microservices:
1. **Authentication Service** verifies your credentials and decodes your token.
2. **Customer Service** fetches your profile and shipping address.
3. **Inventory Service** checks product stock against an operational database.
4. **Pricing Service** computes discounts, coupons, and dynamic taxes.
5. **Payment Gateway** contacts external banking networks to charge your card.
6. **Notification Service** publishes an order confirmation receipt.

In modern enterprise architectures, these steps execute across hundreds of distributed containers in milliseconds. 

When a failure occurs — an order spins endlessly, checkout times out with HTTP 504, or inventory double-deducts — identifying the **true root cause** is notoriously difficult. Was it database IOPS saturation? A downstream transit lag spike? An overloaded payment gateway? A runaway retry storm? Site Reliability Engineers (SREs) routinely spend hours correlating gigabytes of fragmented logs across disjointed observability dashboards.

---

### 🚀 The Solution: TraceMind acts as an Intelligent "MRI Scanner" for Software Workflows
**TraceMind** is an end-to-end, multi-tenant distributed workflow intelligence platform that monitors, diagnoses, optimizes, and autonomously remediates distributed transaction pipelines:

* ⏱️ **Predicts In-Flight Failures**: As a transaction traverses its DAG nodes, supervised XGBoost models predict failure probabilities and latency overruns *while the workflow is still in flight*, explaining exact risk factors via **TreeSHAP** feature attribution waterfalls.
* 🔍 **Multi-Tier Anomaly Detection**: Combines online exponential moving averages (EWMA), statistical IQR/Z-scores, and unsupervised Isolation Forests to flag subtle latency deviations and cascading retry loops.
* 🎯 **Causal Graph Root Cause Analysis (RCA)**: Constructs a causal dependency DAG of the incident, traces error and latency propagation backwards to the root culprit (e.g. *"Inventory DB saturation delayed inventory-service, triggering payment gateway timeouts"*), and ranks competing hypotheses with calibrated statistical confidence.
* 📈 **3D Pareto Path Optimization**: Automatically searches execution paths across the multi-objective Pareto frontier (**Latency vs. Cost vs. Reliability**) to discover optimal routing detours.
* 🛡️ **Autonomous Closed-Loop Remediation**: Synthesizes and executes safe mitigation action plans (concurrency throttling, traffic diversion, circuit breaking) governed by deterministic safety invariant bounds and logged into a **cryptographic SHA-256 Merkle audit ledger**.
* 🧪 **High-Throughput Discrete-Event Simulation**: Includes a built-in simulation engine (**TraceSim**) capable of generating millions of synthetic traces and injecting 7 realistic chaos failure scenarios for benchmark evaluation.

---

## 2. High-Level System Architecture

```text
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                  TRACEMIND END-TO-END DATAFLOW                                          │
 ├─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │                                                                                                         │
 │  1. WORKFLOW TELEMETRY          2. STREAMING INGESTION         3. HYBRID PERSISTENCE                    │
 │  ┌───────────────────────┐      ┌─────────────────────────┐    ┌───────────────────────────────────┐    │
 │  │ 7 Microservices Mesh  │ ───► │ Apache Kafka (KRaft)    │ ──►│ PostgreSQL / TimescaleDB          │    │
 │  │ Discrete TraceSim /   │      │ Micro-Batch Consumer    │    │ Partitioned Hypertables           │    │
 │  │ OpenTelemetry Traces  │      │ (>25k events/sec)       │    │ DuckDB Analytical OLAP            │    │
 │  └───────────────────────┘      └─────────────────────────┘    └───────────────────────────────────┘    │
 │                                                                                  │                      │
 │                                                                                  ▼                      │
 │  6. CLOSED-LOOP ACTUATION       5. 3D PARETO OPTIMIZATION      4. ML DIAGNOSTICS & ROOT CAUSE           │
 │  ┌───────────────────────┐      ┌─────────────────────────┐    ┌───────────────────────────────────┐    │
 │  │ Non-Bypassable Safety │ ◄─── │ Multi-Objective Search  │ ◄──│ XGBoost Failure Predictor         │    │
 │  │ Invariant Evaluator   │      │ Latency vs Cost vs SLA  │    │ TreeSHAP Feature Attributions     │    │
 │  │ In-Memory / Webhook   │      │ Optimal Routing Detours │    │ Composite Anomaly Detection       │    │
 │  │ SHA-256 Audit Ledger  │      │ Transparent Cost Model  │    │ Causal Graph RCA Engine           │    │
 │  └───────────────────────┘      └─────────────────────────┘    └───────────────────────────────────┘    │
 │              │                                                                                          │
 │              ▼                                                                                          │
 │  7. OPERATIONAL DASHBOARD & INTERACTIVE REASONING                                                       │
 │  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐        │
 │  │ React 18 / Vite Real-Time Dashboard (Topologies, Causal Trees, Pareto Curves, Audit Logs)   │        │
 │  │ SSE Streaming AI ReAct Analyst (MockLLM / GPT-4o Support) + OpenTelemetry & Prometheus /    │        │
 │  │ Grafana Observability Suite                                                                 │        │
 │  └─────────────────────────────────────────────────────────────────────────────────────────────┘        │
 └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Product Modules & Completed Capabilities (Milestones 0–15)

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
| **Module 13: Large-Scale HPC Scalability** | Parallel discrete-event trace simulator, streaming chunk pipeline, and 1M+ trace benchmark (18.9M events). | ✅ **Milestone 13 Complete** |
| **Module 14: Autonomous Closed-Loop Remediation** | Self-healing operational runtime control plane with deterministic safety invariants, exact-state rollback, and cryptographic SHA-256 audit ledger. | ✅ **Milestone 14 Complete** |
| **Module 15: Enterprise Multi-Tenancy & Zero-Trust Security** | Tenant-isolated data persistence, RS256 token rotation, AES-256-GCM envelope encryption, and non-bypassable safety invariant guards. | ✅ **Milestone 15 Complete** |

---

## 4. Empirical Benchmarks & Verifiable Evidence

All subsystem benchmarks are empirically verified and reproducible via automated test harnesses:

```text
================================================================================
  TraceMind Milestone Verification & Benchmark Summary
================================================================================
  1. Regression Test Suite              : 162/162 Tests Passing (10.79s execution)    [PASSED]
  2. Static Typing & Linting Quality    : Mypy: 0 errors (144 source files), Ruff OK   [PASSED]
  3. Kafka Ingestion Throughput         : 25,151 events/sec (>5,000 target)           [PASSED]
  4. In-Flight ML Prediction Quality    : ROC-AUC: 0.992, F1-Score: 0.923 (CPU)        [PASSED]
  5. TreeSHAP Additive Consistency      : Exact local fidelity (sum phi_i = f(x)-E[f]) [PASSED]
  6. Anomaly Detection Benchmark Recall : 210/210 detected across chaos test traces    [PASSED]
  7. Nominal False Positive Rate (FPR)  : 3.0% under nominal baseline traffic (< 5%)   [PASSED]
  8. Root-Cause Attribution Accuracy    : 175/175 ground-truth incident evaluations    [PASSED]
  9. RCA Single-Execution Latency       : P50: 0.53ms, P99: 1.15ms (< 10ms target)     [PASSED]
 10. 3D Pareto Optimizer Throughput     : P50: 0.13ms, P99: 0.37ms (6,045+ opt/sec)    [PASSED]
 11. AI Analyst Grounding Fidelity      : P99: 1.51ms, 95.75% grounding, 0% halluc     [PASSED]
 12. Observability Middleware Overhead  : Delta P99: +0.245ms (< 0.500ms target)       [PASSED]
 13. 1M+ Trace HPC Simulation Rate      : 22,120.9 exec/s | 426,239.4 events/s         [PASSED]
 14. Remediation Synthesis Throughput   : 18,981 plans/sec (P99: 0.124ms)              [PASSED]
 15. In-Memory Actuation Speed          : 54,612 actuations/sec (P99: 0.045ms)         [PASSED]
 16. Verbatim Exact Rollback Speed      : 53,792 rollbacks/sec (P99: 0.038ms)          [PASSED]
 17. Deterministic Invariant Fuzzing    : 100/100 unsafe plans rejected (100% gate)    [PASSED]
 18. Cryptographic SHA-256 Ledger Speed : 3,913 entries/sec (100% chain integrity)     [PASSED]
 19. RS256 JWT Token Verification       : 36,498 ops/sec (Mean latency: 27.2 us)       [PASSED]
 20. AES-256-GCM Envelope Encryption    : 290,827 ops/sec (Latency: 3.44 us)           [PASSED]
================================================================================
```

> **Methodology & Context Note**:  
> * **RCA & Anomaly Benchmarks**: Evaluated on synthetic discrete-event chaos injections with deterministic ground-truth labels.  
> * **Microbenchmarks**: Measured in-memory on Intel Core multi-core host CPU with pinned memory baselines.  
> * **HPC Scalability**: Profiled via `benchmarks/benchmark_hpc_scalability.py` maintaining peak memory strictly bounded to $\le 748.2\text{ MB}$.

---

## 5. Technology Stack

* **Core Backend Framework**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (AsyncIO), Alembic, Uvicorn, Structlog.
* **Database & Persistence**: PostgreSQL 16, TimescaleDB (partitioned hypertables), DuckDB (OLAP traces), SQLite/aiosqlite.
* **Streaming & Event Bus**: Apache Kafka 3.7 (KRaft mode, zero ZooKeeper), aiokafka, Micro-Batch Ingestor.
* **Machine Learning & Graph Theory**: XGBoost, Scikit-learn, SHAP (TreeSHAP), NumPy, Pandas, SimPy, NetworkX.
* **Frontend Architecture**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, Canvas/SVG DAG visualizer.
* **Observability & Metrics**: OpenTelemetry (W3C standard), Prometheus Client (`/metrics`), Grafana.
* **Security & Cryptography**: Argon2id password hashing, AES-256-GCM envelope encryption, RS256/Ed25519 JWT signing, SHA-256 Merkle-style audit ledger chaining.
* **Containerization & Orchestration**: Docker (multi-stage non-root builds), Docker Compose, Kubernetes manifests, Devcontainers.
* **Quality Gates & CI**: GitHub Actions, Pytest, Pytest-AsyncIO, Mypy Strict, Ruff.

---

## 6. Quick Start & Demonstration Options

### Option A: 1-Command Local Docker Demo (Recommended)
Runs the entire platform locally with zero external dependencies and zero cloud cost:

```bash
# 1. Clone repository
git clone https://github.com/rishabh211200/TraceMind.git
cd TraceMind

# 2. Start demo container topology (single exposed port 80)
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build

# 3. Seed deterministic telemetry, trained ML models & 4 showcase scenarios (2.2s)
docker compose -f docker-compose.demo.yml exec api python scripts/demo_bootstrap.py

# 4. Open dashboard in browser
# URL: http://localhost
# Admin User: admin@tracemind.io / TraceMind#Admin2026!
# Viewer User: viewer@tracemind.io / Viewer#Demo2026!
```

### Option B: Local Python Development Setup

```bash
# 1. Set up virtual environment
uv venv .venv --python 3.12
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev,ml]"

# 2. Run backend API Gateway
uvicorn apps.api.main:app --reload --port 8000

# 3. In a separate terminal, run frontend
cd frontend
npm install
npm run dev
```

---

## 7. Synthetic Simulation & Chaos Presets (TraceSim CLI)

TraceMind includes a high-performance discrete-event chaos simulator for generating realistic distributed telemetry from the terminal:

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
* `service_failure`: 95% error rate injection simulating microservice process crashes.
* `network_latency`: 180ms transit latency added across inter-service RPC hops.
* `retry_storm`: Cascading retries amplifying load on degraded downstream dependencies.
* `cascading_failure`: Multi-stage cascading failure across database, payment, and order queues.

---

## 8. Enterprise Multi-Tenancy & Zero-Trust Security

TraceMind incorporates enterprise-grade multi-tenancy and Zero-Trust cryptographic security designed for strict data isolation and defense-in-depth:

```text
                        ┌──────────────────────────────────────────────┐
                        │   Inbound HTTP / WebSocket Request          │
                        │   (Authorization: Bearer <RS256 JWT> / Key)  │
                        └──────────────────────┬───────────────────────┘
                                                │
                                                ▼
                        ┌──────────────────────────────────────────────┐
                        │     Zero-Trust Security Gateway / RBAC       │
                        │   - Asymmetric RS256 Signature Verification   │
                        │   - Authoritative JWT Tenant Extraction      │
                        │   - X-Tenant-Id Anti-Spoofing Defense        │
                        │   - Sliding-Window Rate Limiting (797k ops/s)│
                        └──────────────────────┬───────────────────────┘
                                                │
                                                ▼
                        ┌──────────────────────────────────────────────┐
                        │       Tenant-Scoped Execution Context        │
                        │       (Thread-Safe AsyncIO ContextVars)      │
                        └──────────────────────┬───────────────────────┘
                                                │
                ┌───────────────────────────────┼───────────────────────────────┐
                │                               │                               │
                ▼                               ▼                               ▼
     ┌─────────────────────┐         ┌─────────────────────┐         ┌─────────────────────┐
     │ Multi-Tenant DB     │         │ Envelope Encryption │         │ Non-Bypassable M14  │
     │ All models scoped   │         │ AES-256-GCM (v1 tag)│         │ Remediation Safety  │
     │ to tenant_id index  │         │ Argon2id Passwords  │         │ Invariant Guard     │
     └─────────────────────┘         └─────────────────────┘         └─────────────────────┘
```

* **Strict Multi-Tenant Isolation**: All domain models and database tables (`workflows`, `executions`, `traces`, `incidents`, `anomalies`, `predictions`, `root_causes`, `optimizations`, `remediations`, `api_keys`, `users`) contain an indexed `tenant_id` column to prevent IDOR/BOLA cross-tenant data leaks.
* **Authoritative Tenant Claims**: Inbound JWT claims dictate tenant identity; mismatches between `X-Tenant-Id` and token claims are rejected with `403 Forbidden`.
* **Asymmetric RS256 Token Lifecycle**: 15-minute access tokens with 7-day single-use refresh token rotation and database revocation blocklisting.
* **Hierarchical RBAC Matrix**: 5 roles (`PLATFORM_ADMIN`, `TENANT_ADMIN`, `OPERATOR`, `ANALYST`, `VIEWER`) across 24 granular permissions.
* **Envelope Encryption**: Sensitive integrations encrypted with versioned `AES-256-GCM` envelopes (`v1:<key_id>:<nonce>:<ciphertext>:<tag>`).
* **Non-Bypassable Remediation Shield**: Automated and manual remediation actions are validated by deterministic safety guards enforcing blast radius ($\le 30\%$), acyclicity, and capacity headroom bounds.

---

## 9. Documentation & Research Sitemap

* **Demonstration Walkthrough Guide**: [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md)
* **Showcase & Release Audit**: [`docs/SHOWCASE_READINESS_AUDIT.md`](docs/SHOWCASE_READINESS_AUDIT.md)
* **HPC Scalability Research Whitepaper (1M+ Traces)**: [`docs/research/hpc_scalability_report.md`](docs/research/hpc_scalability_report.md)
* **Architecture Specifications**:
  * [Persistence & Telemetry Schema](docs/architecture/persistence.md)
  * [Observability & OpenTelemetry](docs/architecture/observability.md)
  * [Production Deployment & Containerization](docs/architecture/deployment.md)
* **Milestone Execution History**: [`docs/project-history.md`](docs/project-history.md)

---

## 10. License

This project is licensed under the terms of the [MIT License](LICENSE).
