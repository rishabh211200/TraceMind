# TraceMind — Project Engineering History & Chronological Log

This document serves as the persistent, chronological engineering record of **TraceMind**. It details the architectural decisions, component implementations, verification benchmarks, audits, and Git history milestone-by-milestone.

---

## Milestone 0: Repository Foundation & Monorepo Architecture

* **Status**: Completed
* **Initial Commit**: `8ca73de113b7764fc4fcb09ef521a81d84ce194d` (`chore: initialize TraceMind project foundation`)
* **Subsequent Maintenance Commit**: `95c5a6759b125e371570ca045f43d73eee003c4f` (`fix(ci): upgrade setup-uv to v5 and node to v24 with uv.lock cache`)
* **Branch**: `main`

### 1. Project Vision & Objective
TraceMind is an end-to-end AI-powered distributed workflow intelligence platform designed to ingest high-throughput distributed trace telemetry, predict in-flight execution failures and latency degradation, detect unmodeled system anomalies, perform graph-grounded root cause analysis (RCA), optimize multi-path workflow topologies, and provide an interactive tool-grounded AI Analyst.

### 2. Architecture & Monorepo Topology
Milestone 0 established a structured, production-grade monorepo architecture separating runnable applications, modular packages, frontend UI, container configurations, and formal documentation:

```text
TraceMind/
├── apps/                        # Application entrypoints
│   ├── api/                     # FastAPI core backend & routing
│   └── simulator/               # TraceSim distributed system simulation engine
├── packages/                    # Reusable domain, telemetry, and common libraries
│   ├── common/                  # Configuration (pydantic-settings), structured logging (structlog)
│   ├── database/                # SQLAlchemy models, session managers, repository layers
│   └── domain/                  # Pydantic v2 domain schemas (events, services, workflows, incidents)
├── frontend/                    # React 18 + TypeScript + Vite + Tailwind CSS dashboard
├── infrastructure/              # Multi-stage Dockerfiles and deployment manifests
│   └── docker/                  # Dockerfile.api, Dockerfile.frontend
├── migrations/                  # Alembic database migration environment
├── docs/                        # Specifications, research documents, and architecture ADRs
│   ├── adr/                     # Architecture Decision Records (ADR-001)
│   ├── architecture/            # System architecture overview and component specs
│   ├── research/                # Dataset definitions and statistical formulations
│   └── roadmap.md               # 14-milestone engineering roadmap
└── tests/                       # Automated test suites
    ├── unit/                    # Unit tests for domain models, config, and simulator
    └── integration/             # End-to-end integration and API contract verification
```

### 3. Toolchain & Quality Gates
* **Python Runtime**: Python 3.12 (`cpython-3.12.14`).
* **Package & Environment Management**: Astral `uv` for ultra-fast, deterministic virtual environments and locked dependency resolution (`uv.lock`).
* **Core API Framework**: FastAPI with Pydantic v2 domain serialization and OpenAPI v3 auto-generation (`/docs`, `/redoc`).
* **Frontend Stack**: React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, dark-themed developer dashboard skeleton.
* **Infrastructure**: Docker Compose defining PostgreSQL 16 + TimescaleDB, Redis 7 Alpine, API, and Frontend with automated health checks.
* **Database & Migration Framework**: SQLAlchemy 2.0 (AsyncIO) with `asyncpg` and Alembic.
* **Static Analysis & Linting**: Ruff for formatting and linting (E, F, B, I, C, UP rules) and Mypy for static type checking across `packages/`, `apps/`, and `tests/`.
* **Test Framework**: Pytest with `pytest-asyncio` and `pytest-cov`.
* **CI/CD Pipeline**: GitHub Actions (`.github/workflows/ci.yml`) testing Python 3.12 lint, type checking, test coverage, and Frontend Vite production build on every push and pull request.
* **Architecture Decision Record**: [ADR-001: Project Foundation and Architectural Standards](file:///c:/Users/Rishabh.Gupta/Personal_Projects/TraceMind/docs/adr/ADR-001-project-foundation.md).

---

## Milestone 1: TraceSim — Synthetic Distributed System Simulator

* **Status**: Completed & Audited
* **Primary Implementation Commit**: `defaa75` (`feat(simulator): implement TraceSim synthetic distributed trace simulator (Milestone 1)`)
* **Audit Alignment Commit**: `c551091` (`fix(simulator): align database infrastructure model and enhance ground-truth trace tagging`)
* **Branch**: `feat/trace-sim`

### 1. Purpose & Motivation
Real-world distributed trace data with verified ground-truth failure annotations is notoriously rare, sensitive, and difficult to obtain from production environments. TraceSim exists to generate high-fidelity, causally consistent synthetic distributed trace datasets. It acts as the ground-truth benchmark generator for downstream machine learning experiments (failure prediction, anomaly detection, TreeSHAP feature attribution, and graph root-cause analysis) without requiring live distributed clusters.

### 2. Core Components Implemented
* **Configuration Layer (`apps/simulator/config.py`)**:
  * Baseline profiles for the 7 business microservices.
  * Workload presets (`SMALL=1,000`, `MEDIUM=10,000`, `LARGE=100,000`, `CUSTOM`).
  * Export format selectors (`JSONL`, `PARQUET`, `ALL`).
* **Deterministic Distribution Sampler (`apps/simulator/distributions.py`)**:
  * Mean-adjusted **Log-Normal** latency distribution: $\mu = \ln(\text{mean}) - \frac{1}{2}\sigma^2$, ensuring that $\mathbb{E}[X]$ equals nominal baseline while generating heavy right-tailed latencies.
  * Natural latency spikes (e.g. host garbage collection, network jitter) scaling nominal latency by $3.5\times$ with $2\%$ stochastic probability.
  * Bernoulli trials for cache hits and transient failures.
  * Exponential retry backoff with full jitter: $t_{\text{backoff}} = \text{base} \cdot 2^{\text{attempt}} \cdot \text{Uniform}(0.5, 1.5)$.
  * Poisson inter-arrival time generator based on arrival rate $\lambda$.
* **Causal Chaos Incident Engine (`apps/simulator/incidents.py`)**:
  * Schedules controlled chaos scenarios across simulated time windows.
  * Computes dynamic service degradation modifiers (`ServiceDegradationModifier`) altering latency multipliers, failure rates, capacity, and network transit delays.
* **Simulated Service Actor (`apps/simulator/services.py`)**:
  * Models in-flight concurrency queues, calculating queueing delay when concurrent load exceeds capacity:
    $$\Delta t_{\text{queue}} = \left(\frac{\text{in\_flight} - \text{capacity}}{\text{capacity}}\right) \cdot \text{baseline} \cdot 1.5$$
  * Client timeout threshold evaluation (`timeout_ms`).
  * Automatic retry loop with backoff and emission of `RETRY_STARTED`, `RETRY_COMPLETED`, `SERVICE_FAILED`, and `SERVICE_TIMEOUT` events.
* **Workflow Engine (`apps/simulator/workflow_engine.py`)**:
  * Executes multi-hop business workflows while maintaining causal parent-child span linkage, trace correlation IDs, and monotonic timestamps.
* **Streaming Dataset Exporter (`apps/simulator/exporter.py`)**:
  * High-throughput serialization to `executions.jsonl`, `events.jsonl`, `incidents.jsonl` and `executions.parquet`, `events.parquet`, `incidents.parquet` via PyArrow.
* **Statistical Reporting & CLI (`apps/simulator/stats.py`, `apps/simulator/cli.py`, `apps/simulator/__main__.py`)**:
  * Console dashboard computing P50, P90, P95, P99 latency percentiles, retry frequency, timeout count, and incident breakdown.

### 3. Supported Chaos Scenarios & Causal Chains
1. **`DATABASE_LATENCY`**: Database storage I/O bottleneck degrades `customer-db` and `inventory-db` by $5.5\times$ $\rightarrow$ propagates latency to `customer-service` and `inventory-service` $\rightarrow$ causally delays downstream dependent calls (`payment-service`, `order-service`) $\rightarrow$ elevated workflow P95 latency (1,329ms vs 758ms baseline).
2. **`TRAFFIC_SPIKE`**: Workload arrival rate surges $5\times$ ($100\text{ req/sec}$) $\rightarrow$ in-flight concurrency exceeds service capacity $\rightarrow$ non-linear queue delay accumulates across all services $\rightarrow$ P95 latency increases from 758ms to 1,080ms.
3. **`PAYMENT_LATENCY_DEGRADATION`**: Payment gateway latency spikes $4.0\times$, error rate increases to $45\%$ $\rightarrow$ triggers retry backoff $\rightarrow$ operations exceeding timeout threshold (3,500ms) emit `SERVICE_TIMEOUT` $\rightarrow$ order service is skipped $\rightarrow$ workflow terminates in failure ($23.8\%$ retries).
4. **`SERVICE_FAILURE`**: Target service (`inventory-service`) experiences $95\%$ failure rate $\rightarrow$ retries exhausted ($87.3\%$ retry rate) $\rightarrow$ fast workflow termination ($25.2\%$ failure rate over run, $>80\%$ during incident window).
5. **`NETWORK_LATENCY`**: Transit latency ($+150\text{ms}$) injected across inter-service RPC hops $\rightarrow$ cumulative workflow duration increases by $\sim 1,050\text{ms}$ (P95: 2,270ms vs 758ms baseline).
6. **`RETRY_STORM`**: Upstream flakiness triggers cascading client retries $\rightarrow$ retries amplify concurrency load $\rightarrow$ P99 latency surges to 5,150ms ($34.9\%$ retry rate).
7. **`CASCADING_FAILURE`**: Compound failure: DB latency $4.0\times$ $\rightarrow$ payment gateway latency $3.5\times$ + $50\%$ error rate $\rightarrow$ order queue exhaustion (P99: 5,681ms, $32.9\%$ retries).

### 4. Architecture Alignment & Audit Corrections
During the post-implementation architecture audit, the domain model was audited to ensure infrastructure dependencies are strictly separated from business microservices:
* **Business Microservices (7)**: `auth-service`, `customer-service`, `inventory-service`, `pricing-service`, `payment-service`, `order-service`, `notification-service`.
* **Infrastructure Dependencies**:
  * `customer-cache` (cache lookup: ~85% hit / ~15% miss)
  * `customer-db` (query fallback on cache miss: `DATABASE_QUERY`)
  * `inventory-db` (stock reservation queries: `DATABASE_QUERY`)
  * `payment-gateway` (external payment processor)
* **Ground-Truth Metadata**: Added direct `incident_id` and `is_incident_affected` tags to `WorkflowExecution.metadata` and `TraceEvent.metadata` to ensure effortless labeling for ML pipelines without table joins.

### 5. Verification & Benchmark Results
* **Test Suite**: 26/26 tests passed in **1.16s** (`test_simulator.py`, `test_incidents.py`, `test_simulator_regression.py`, `test_simulation_pipeline.py`).
* **Static Analysis**: Mypy clean across 39 source files; Ruff lint and format clean across 54 files.
* **10,000 Workflow Generation Benchmark**:
  * Generation wall time: **1.80s** (**5,561 workflows/sec**).
  * Emitted **173,826 trace events**.
  * Parquet sizes: `executions.parquet` (412 KB), `events.parquet` (3.2 MB), `incidents.parquet` (7.2 KB).
* **Determinism**: Identical seed (42) produced bit-exact matching execution counts, event sequences, latencies, and summary statistics across multiple runs.
---

## Milestone 2: Telemetry Persistence & Query Engine

* **Status**: Completed
* **Branch**: `feat/persistence`
* **Architecture Specification**: [`docs/architecture/persistence.md`](file:///c:/Users/Rishabh.Gupta/Personal_Projects/TraceMind/docs/architecture/persistence.md)

### 1. Purpose & Objectives
Milestone 2 bridges synthetic trace generation with relational storage and analytical time-series querying. It introduces a high-performance persistence engine capable of ingesting high-volume TraceSim telemetry (`executions.parquet`, `events.parquet`, `incidents.parquet`), storing trace spans in a **TimescaleDB hypertable**, performing database-side latency percentiles, reconstructing trace DAG trees in linear time, and exposing query endpoints via FastAPI.

### 2. Core Components Implemented
* **Declarative ORM Models (`packages/database/models/`)**:
  * `ServiceModel` (`services` table): Service identity, type, concurrency capacity, baseline latency/failure, timeout, and retry configuration.
  * `WorkflowDefinitionModel` (`workflow_definitions` table): Static workflow topology definition with nodes and edges.
  * `WorkflowExecutionModel` (`workflow_executions` table): Execution lifecycle records with timestamps, duration, status, retry/error counts, failure reasons, and incident tags.
  * `TraceEventModel` (`trace_events` table): High-volume span telemetry with **composite primary key `(event_id, timestamp)`** and composite indexes `(execution_id, timestamp)`, `(service, timestamp)`, `(event_type, timestamp)`, `(status, timestamp)`, `(parent_event_id)`.
  * `IncidentModel` (`incidents` table): Ground-truth incident records with active time windows, affected services, parameters, and root-cause annotations.
* **Alembic Database Migrations (`migrations/`)**:
  * `001_initial_persistence_schema.py`: Initial schema creating all 5 tables and executing `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE; SELECT create_hypertable('trace_events', 'timestamp', if_not_exists => TRUE);`.
  * Updated `migrations/env.py` to bind dynamically to `Base.metadata`.
* **Async Session & Connection Pooling (`packages/database/session.py`)**:
  * Configures `create_async_engine` with connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`) and `get_db_session()` dependency.
* **Async Repository Layer (`packages/database/repositories/`)**:
  * `ServiceRepository`: CRUD operations and service registry queries.
  * `WorkflowRepository`: Definitions management, execution trace lookups, and multi-parameter filtering (`status`, `incident_id`, `start_time`, `end_time`).
  * `TraceEventRepository`: Chronological span retrieval, linear-time $\mathcal{O}(N)$ DAG tree reconstruction, database-side latency percentiles (`percentile_cont`), and service operational health summaries.
  * `IncidentRepository`: Incident lookups, time-window filtering, and incident-affected trace queries.
* **Bulk Ingestion Pipeline (`packages/database/ingestion.py`)**:
  * `DatasetIngestor`: Ingests Parquet/JSONL datasets in chunked batches (5,000 events/batch) with idempotency fallback.
  * CLI interface: `python -m packages.database.ingestion --input-dir data/generated`.
* **FastAPI Query Endpoints (`apps/api/routes/`)**:
  * `GET /api/v1/traces/{trace_id}`, `GET /api/v1/traces/{trace_id}/events`, `GET /api/v1/traces/{trace_id}/tree`, `GET /api/v1/traces`.
  * `GET /api/v1/services`, `GET /api/v1/services/{service}/latency`, `GET /api/v1/services/{service}/health`, `GET /api/v1/services/telemetry/summary`.
  * `GET /api/v1/incidents`, `GET /api/v1/incidents/{incident_id}`, `GET /api/v1/incidents/{incident_id}/traces`.

### 3. Key Design Decisions
1. **TimescaleDB Composite Primary Key**: TimescaleDB requires unique constraints on hypertables to include the partitioning column (`timestamp`). Defining `PRIMARY KEY (event_id, timestamp)` satisfies TimescaleDB chunk routing while guaranteeing event uniqueness.
2. **Database-Side Aggregations**: Latency percentiles (P50, P90, P95, P99) are computed inside PostgreSQL/TimescaleDB using `PERCENTILE_CONT(...) WITHIN GROUP (ORDER BY latency_ms)` rather than transmitting raw event arrays across the network.
3. **Idempotency Guarantees**: Re-running ingestion on the same dataset produces 0 duplicate records without primary key violation errors.

### 4. Verification & Benchmark Results
* **Test Suite**: 39/39 unit and integration tests passing in **2.49s** (`test_persistence_models.py`, `test_repositories.py`, `test_ingestion.py`, `test_trace_queries.py`, `test_api_persistence_endpoints.py`, `test_simulator.py`, `test_incidents.py`, `test_simulation_pipeline.py`).
* **Static Analysis**: Mypy clean across 61 source files (0 errors); Ruff check and formatting clean across 78 source files.
* **10,000 Workflow Ingestion Benchmark (192,059 Events)**:
  * Generated 10,000 workflows (**192,059 trace events**) in 2.26s.
  * Ingested into database in **13.08s** (**14,687 events/sec** | **765 workflows/sec**).
  * Single execution lookup latency: **P50 = 0.133ms** | **P95 = 0.270ms**.
  * Trace chronological events retrieval (19 spans): **P50 = 0.319ms** | **P95 = 0.513ms**.
  * Trace DAG tree reconstruction: **P50 = 0.397ms** | **P95 = 0.636ms** (1,000-run mean: 0.431ms).
  * Service latency percentiles (192K events): **P50 = 21.314ms** | **P95 = 224.616ms**.
  * Service health & error rates: **P50 = 34.821ms** | **P95 = 239.815ms**.

### 5. Final Performance Optimization: Single-Pass Telemetry Aggregation
* **Problem**: `get_service_telemetry_summary()` previously performed $N$ sequential service-health queries after discovering distinct services ($\sim 578\text{ms}$ total round trips).
* **Solution**: Replaced sequential loop with a single database-side `GROUP BY service` aggregation query computing event totals, failure rates, retry counts, timeout rates, and latency distributions in 1 database pass on PostgreSQL (2 queries in SQLite).
* **Equivalence**: Verified 100% numerical and structural equivalence across all 12 services in `test_optimized_telemetry_summary_correctness_and_filters`.

---
