# TraceMind

**AI-Powered Distributed Workflow Intelligence Platform**

[![CI Pipeline](https://github.com/rishabh211200/TraceMind/actions/workflows/ci.yml/badge.svg)](https://github.com/rishabh211200/TraceMind/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

---

## 1. Overview

**TraceMind** is an experimental AI and research platform engineered to learn behavioral patterns from distributed system workflow execution traces. In complex multi-service architectures, understanding whether an ongoing workflow will succeed, predicting latency degradations, pinpointing cascading dependency failures, and optimizing routing strategies in real time is a critical operational challenge.

TraceMind tackles this using a combination of **discrete-event simulation**, **statistical graph mining**, **supervised failure/latency ML models**, **unsupervised anomaly detection**, **deterministic root-cause reasoning**, and **tool-grounded AI analysis**.

> **Domain-Neutral Architecture**: TraceMind simulates generic distributed microservices (e.g., *Auth Service*, *Customer Service*, *Inventory Service*, *Pricing Service*, *Payment Service*, *Order Service*, *Notification Service*) with realistic latencies, concurrency limits, retries, timeouts, and cascading failure scenarios. All simulation data is completely synthetic and reproducible.

---

## 2. High-Level Architecture

```text
                             ┌────────────────────────┐
                             │  React + TypeScript UI │
                             │  (Vite + Tailwind CSS) │
                             └───────────┬────────────┘
                                         │
                                         ▼
                             ┌────────────────────────┐
                             │    FastAPI Gateway     │
                             │ (OpenAPI / Async REST) │
                             └───────────┬────────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 │                       │                       │
                 ▼                       ▼                       ▼
      ┌──────────────────────┐┌──────────────────────┐┌──────────────────────┐
      │   Workflow Service   ││ Intelligence Service ││      ML Service      │
      │  (Graph Construction)││  (Anomalies & RCA)   ││  (XGBoost / SHAP)    │
      └──────────────────────┘└──────────────────────┘└──────────────────────┘
                 │                       │                       │
                 └───────────────────────┼───────────────────────┘
                                         │
                                         ▼
                             ┌────────────────────────┐
                             │  Event Streaming Layer │
                             │        (Kafka)         │
                             └───────────┬────────────┘
                                         │
                      ┌──────────────────┴──────────────────┐
                      ▼                                     ▼
           ┌─────────────────────┐               ┌─────────────────────┐
           │ TraceSim Simulator  │               │ TimescaleDB / PG    │
           │ (SimPy Engine)      │               │ (Trace Store)       │
           └─────────────────────┘               └─────────────────────┘
```

---

## 3. Product Modules

| Module | Name | Description |
|---|---|---|
| **Module A** | **TraceSim** | High-throughput deterministic discrete-event simulator for distributed microservice workflows. |
| **Module B** | **Trace Store** | High-performance storage and indexing for workflow executions, spans, and lifecycle events. |
| **Module C** | **Workflow Intelligence** | Graph-based workflow mining, node frequency, transition metrics, and topology discovery. |
| **Module D** | **ML Engine** | Supervised models (XGBoost, Random Forest) for pre-completion failure and latency prediction with SHAP explainability. |
| **Module E** | **Root Cause Engine** | Deterministic graph and statistical reasoning engine identifying culprit services with confidence scoring. |
| **Module F** | **Workflow Optimizer** | Historical and multi-objective routing optimizer calculating optimal execution paths. |
| **Module G** | **AI Analyst** | Tool-augmented LLM interface delivering safe, grounded technical explanations of system incidents. |
| **Module H** | **Web Dashboard** | Developer-focused React dashboard with interactive workflow graphs (React Flow) and telemetry drill-downs. |
| **Module I** | **Observability** | Self-monitoring stack using OpenTelemetry, Prometheus metrics, and structured JSON logs. |

---

## 4. Key Capabilities

* **Deterministic Synthetic Tracing**: Seeded generation of multi-branch, parallel, retry-heavy workflow executions.
* **Controlled Chaos Scenarios**: Injected traffic spikes, database saturation, payment gateway latency, network partitions, and cascading failures with ground-truth causal tracking.
* **Pre-Completion Failure Prediction**: Predicts workflow failure while execution is in-flight using cumulative features.
* **SHAP Attribution**: Transparent feature-level breakdown explaining why a workflow was flagged as high-risk.
* **Deterministic Root Cause Hypotheses**: Graphs causal degradation paths prior to AI synthesis, preventing hallucination.
* **Agnostic LLM Integration**: Tool-calling interface where AI can inspect metrics, traces, and graph paths without direct database access.

---

## 5. Technology Stack

* **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (AsyncIO), Alembic, Uvicorn, Structlog.
* **Simulation & ML**: SimPy, NumPy, Pandas, Scikit-learn, XGBoost, SHAP, NetworkX.
* **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, React Flow.
* **Storage & Streaming**: PostgreSQL / TimescaleDB, Redis, Apache Kafka.
* **Quality & CI**: Ruff, Mypy, Pytest, Pytest-AsyncIO, Docker, Docker Compose, GitHub Actions.

---

## 6. Quick Start

### Prerequisites
* Python 3.12+ (or [uv](https://github.com/astral-sh/uv))
* Node.js 20+ & npm
* Docker & Docker Compose (optional for local infrastructure)

### Local Development Setup

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

4. **Initialize Environment Variables**:
   ```bash
   cp .env.example .env
   ```

5. **Start API Server**:
   ```bash
   uvicorn apps.api.main:app --reload --port 8000
   ```
   Open API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

6. **Start Frontend Dashboard**:
   ```bash
   cd frontend
   npm run dev
   ```
   Open Dashboard: [http://localhost:5173](http://localhost:5173)

---

## 7. Generate Synthetic Data (TraceSim CLI)

TraceMind includes a high-performance, deterministic discrete-event simulator for distributed microservice workflows:

```bash
# Generate 10,000 synthetic workflows with default baseline conditions
python -m apps.simulator --workflows 10000 --seed 42

# Inject a specific chaos incident scenario (e.g. Database Latency degradation)
python -m apps.simulator --workflows 5000 --seed 42 --incident database_latency

# Run with custom output directory and format (Parquet & JSONL)
python -m apps.simulator --workflows 10000 --seed 42 --output-dir data/generated --format all
```

Supported chaos scenarios:
* `database_latency`: 5.5x database latency spike propagating to dependent customer, inventory, and payment services.
* `payment_degradation`: 4.2x payment latency degradation and HTTP 504 gateway timeouts.
* `traffic_spike`: 5x surge in workflow arrival rate, saturating service concurrency and driving queueing delays.
* `service_failure`: 95% error rate injection simulating service crash.
* `network_latency`: 180ms transit latency added across all inter-service RPC invocations.
* `retry_storm`: Cascading retries amplifying load on degraded dependencies.
* `cascading_failure`: Multi-stage cascading failure across database, payment, and order queues.

See [docs/research/simulator-dataset.md](docs/research/simulator-dataset.md) for full dataset schemas and distribution models.

---

## 8. Running with Docker Compose

To launch the complete local stack (PostgreSQL TimescaleDB, Redis, API, and Frontend):

```bash
docker compose up -d
```

---

## 9. Verification & Testing

TraceMind enforces rigorous test coverage across domain logic, simulation determinism, API contracts, and ML pipelines:

```bash
# Run unit and integration tests
pytest tests/ -v

# Run linting and code formatting checks
ruff check .
ruff format --check .

# Run static type checking
mypy packages apps tests

# Run frontend build verification
cd frontend && npm run build
```

---

## 10. Development Roadmap

| Milestone | Scope | Status |
|---|---|---|
| **Milestone 0** | Repository Foundation, Architecture, CI/CD, Docs | **Completed** |
| **Milestone 1** | TraceSim Engine & Synthetic Event Generation | **Completed** |
| **Milestone 2** | PostgreSQL / TimescaleDB Persistence & Querying | Upcoming |
| **Milestone 3** | FastAPI Workflow, Execution, and Simulation APIs | Planned |
| **Milestone 4** | React/TypeScript Interactive Web Dashboard | Planned |
| **Milestone 5** | Kafka Event Streaming & Async Pipeline | Planned |
| **Milestone 6** | Failure & Latency ML Prediction Pipeline | Planned |
| **Milestone 7** | Unsupervised Anomaly Detection | Planned |
| **Milestone 8** | Graph-Based Root Cause Engine | Planned |
| **Milestone 9** | Workflow Optimization & Path Routing | Planned |
| **Milestone 10** | Tool-Grounded AI Analyst | Planned |
| **Milestone 11** | OpenTelemetry & Prometheus Observability | Planned |
| **Milestone 12** | Containerized Cloud Deployment | Planned |
| **Milestone 13** | Large-Scale HPC Performance Benchmarking | Planned |

See [docs/roadmap.md](docs/roadmap.md) for detailed deliverables.

---

## 11. License

This project is licensed under the terms of the [MIT License](LICENSE).