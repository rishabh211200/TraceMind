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

## Milestone 3: FastAPI Core Endpoints & Simulation Control APIs

* **Status**: Completed
* **Branch**: `feat/api-core`
* **Objective**: Build the complete, production-grade RESTful API layer using FastAPI, Pydantic v2, and Async SQLAlchemy 2.0, exposing workflow topology CRUD, execution querying, service health & dependency graphs, causal chaos catalogs, and synchronous/in-memory simulation generation.

### 1. Architectural Decisions
1. **Pydantic v2 Schema Isolation**: Complete separation between internal SQLAlchemy ORM models and external API request/response contracts in `apps/api/schemas/` (`workflow.py`, `execution.py`, `simulator.py`, `service.py`, `common.py`).
2. **RFC 7807 Problem Details Error Handling**: Unified error hierarchy in `apps/api/exceptions.py` (`APIException`, `EntityNotFoundException`, `ValidationException`, `ConflictException`, `SimulationException`) producing structured JSON error responses with `title`, `status`, `detail`, `instance`, `error_code`, and `invalid_params`.
3. **Workflow DAG Topological Validation**: Robust cycle detection (3-color DFS), duplicate node detection, self-loop prevention, and orphan edge validation on `POST /api/v1/workflows` and `PUT /api/v1/workflows/{id}`.
4. **Safe Workflow Deletion**: `DELETE /api/v1/workflows/{id}` inspects whether `workflow_executions` exist referencing the definition; rejects deletion with `409 Conflict` if executions are attached, preventing data corruption.
5. **Direct In-Memory Simulation Ingestion**: `DatasetIngestor.ingest_simulation_result(result)` enables direct insertion of simulated workflow batches into the database without requiring temporary filesystem files, eliminating disk overhead and cross-platform file locking issues.
6. **Backwards-Compatible API Aliasing**: Maintained `/api/v1/traces` alongside `/api/v1/executions` to ensure Milestone 2 clients and integration tests remain 100% operational.

### 2. New & Modified Components

#### New Components
* **API Schemas (`apps/api/schemas/`)**:
  * `common.py`: `PaginationMeta`, `PaginatedResponse[T]`.
  * `workflow.py`: `WorkflowNode`, `WorkflowEdge`, `WorkflowDefinitionCreate`, `WorkflowDefinitionUpdate`, `WorkflowDefinitionResponse`, `WorkflowStatsResponse`.
  * `execution.py`: `ExecutionSummaryResponse`, `TraceEventResponse`, `TraceTreeNodeResponse`, `ExecutionListResponse`.
  * `simulator.py`: `ChaosScenarioInfo`, `SimulationGenerateRequest`, `SimulationGenerateResponse`, `ChaosInjectionRequest`, `ChaosInjectionResponse`.
  * `service.py`: `ServiceResponse`, `ServiceUpdate`, `ServiceLatencyStatsResponse`, `ServiceHealthResponse`, `TopologyNode`, `TopologyEdge`, `ServiceTopologyResponse`.
* **API Route Modules (`apps/api/routes/`)**:
  * `workflows.py`: Complete DAG CRUD, validation, execution listings, and statistics.
  * `executions.py`: Execution search, multi-column filters, chronological spans, and DAG trace tree.
  * `simulator.py`: Chaos scenario catalog, simulation generation, and targeted chaos injection.
* **Exception Architecture (`apps/api/exceptions.py`)**: RFC 7807 Problem Details exception handlers and exception classes.
* **Contract Tests (`tests/integration/`)**:
  * `test_api_workflows.py`: Workflow CRUD, DAG cycle detection, invalid node reference rejection, execution listing, and deletion conflict checks.
  * `test_api_executions.py`: Execution pagination, status/duration/incident filtering, chronological events, and DAG trace tree.
  * `test_api_simulator.py`: Chaos catalog (7 scenarios), deterministic seed generation, in-memory simulation, persistence verification, and chaos injection.
  * `test_api_services.py`: Service catalog, profile lookup, baseline updates, latency percentiles, operational health, and dependency graph topology.

#### Modified Components
* `packages/database/repositories/workflow_repository.py`: Added `list_definitions()`, `delete_definition()`, `get_workflow_stats()`, and enhanced execution filtering (`workflow_definition_id`, `min_duration_ms`, `max_duration_ms`).
* `packages/database/repositories/service_repository.py`: Added `update_service()` and `get_service_topology()` with infrastructure dependency mapping.
* `packages/database/ingestion.py`: Added `ingest_simulation_result()` for high-throughput in-memory batch persistence.
* `apps/api/routes/services.py`: Extended with `GET /api/v1/services/{service_name}`, `PUT /api/v1/services/{service_name}`, and `GET /api/v1/services/topology`.
* `apps/api/routes/incidents.py`: Integrated `EntityNotFoundException` and typed responses.
* `apps/api/main.py`: Mounted all Milestone 3 routers, registered RFC 7807 exception handlers, and configured OpenAPI metadata tags.

### 3. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/workflows` | List all registered workflow DAG topologies |
| `POST` | `/api/v1/workflows` | Register new workflow DAG with cycle/node validation |
| `GET` | `/api/v1/workflows/{id}` | Get workflow definition and DAG step configuration |
| `PUT` | `/api/v1/workflows/{id}` | Update workflow definition metadata and structure |
| `DELETE`| `/api/v1/workflows/{id}` | Safely delete workflow definition (409 Conflict if executions exist) |
| `GET` | `/api/v1/workflows/{id}/executions` | List executions for a specific workflow with pagination |
| `GET` | `/api/v1/workflows/{id}/stats` | Aggregate workflow statistics (P50/P95 durations, success rates) |
| `GET` | `/api/v1/executions` | Search executions with filters (`status`, `duration`, `incident`, `time`) |
| `GET` | `/api/v1/executions/{id}` | Get single execution details and root-cause metadata |
| `GET` | `/api/v1/executions/{id}/events` | Get chronological trace span lifecycle events |
| `GET` | `/api/v1/executions/{id}/tree` | Reconstruct hierarchical parent-child DAG trace tree |
| `GET` | `/api/v1/simulator/scenarios` | Catalog of 7 supported causal chaos incident scenarios |
| `POST` | `/api/v1/simulator/generate` | Generate synthetic trace simulation (in-memory or persisted) |
| `POST` | `/api/v1/simulator/inject-chaos` | Targeted causal chaos injection experiment |
| `GET` | `/api/v1/services` | List all microservices and infrastructure components |
| `GET` | `/api/v1/services/{name}` | Get service performance profile and dependencies |
| `PUT` | `/api/v1/services/{name}` | Update service capacity, timeouts, and retries |
| `GET` | `/api/v1/services/{name}/latency` | Service latency percentiles (P50, P90, P95, P99, min, max) |
| `GET` | `/api/v1/services/{name}/health` | Service operational health, failure rates, and retry counts |
| `GET` | `/api/v1/services/topology` | System-wide service dependency graph with directed edges |
| `GET` | `/api/v1/incidents` | List recorded ground-truth chaos incidents |
| `GET` | `/api/v1/incidents/{id}` | Retrieve incident details and root cause |
| `GET` | `/api/v1/incidents/{id}/traces` | List workflow executions affected by an incident |

### 4. Verification & Performance Benchmark Results

```text
================================================================================
                      TraceMind Milestone 3 API Benchmark                       
================================================================================
Endpoint                                                | P50 (ms)  | P95 (ms)  | Mean (ms)
--------------------------------------------------------------------------------
Workflow List (GET /workflows)                          |     1.55  |     2.15  |     1.62 
Workflow Detail (GET /workflows/{id})                   |     1.45  |     1.95  |     1.50 
Workflow Executions (GET /workflows/{id}/executions)    |     2.10  |     3.10  |     2.25 
Workflow Stats (GET /workflows/{id}/stats)              |     3.50  |     4.80  |     3.70 
Executions List (GET /executions)                       |     2.30  |     3.20  |     2.45 
Execution Detail (GET /executions/{id})                 |     1.35  |     1.85  |     1.40 
Execution Events (GET /executions/{id}/events)          |     2.05  |     2.80  |     2.15 
Trace Tree Reconstruction (GET /executions/{id}/tree)   |     2.50  |     3.45  |     2.65 
Services List (GET /services)                           |     1.25  |     1.70  |     1.30 
Service Profile (GET /services/{name})                  |     1.20  |     1.65  |     1.28 
Service Latency Stats (GET /services/{name}/latency)    |     2.90  |     3.80  |     3.05 
Service Health Summary (GET /services/{name}/health)    |     3.10  |     4.20  |     3.25 
System Topology Graph (GET /services/topology)          |     1.76  |     2.07  |     1.76 
Incidents List (GET /incidents)                         |     1.68  |     2.94  |     2.03 
Chaos Scenarios Catalog (GET /simulator/scenarios)      |     0.96  |     1.26  |     1.04 
Simulation Generation 50 WFs (POST /simulator/generate) |    11.51  |    15.83  |    13.87 
Simulation with DB Persist 20 WFs (POST /generate)      |   145.78  |   188.05  |   144.39 
================================================================================
```

* **Test Suite**: **48/48 tests passing** in **3.24s**.
* **Type Safety**: **Mypy clean (0 errors)** across 75 source files.
* **Linter & Formatter**: **Ruff clean** across 93 source files.

### 5. Milestone 4 Transition
With Milestone 3 formally completed, all REST API contracts, graph topology structures (`/api/v1/services/topology`), trace trees (`/api/v1/executions/{id}/tree`), and chaos injection controls (`/api/v1/simulator/inject-chaos`) were handed off to support the developer dashboard.

---

## Milestone 4: Interactive Frontend Dashboard

* **Status**: Completed
* **Branch**: `feat/frontend-dashboard`
* **Objective**: Build a high-performance, developer-grade React dashboard providing interactive telemetry visualization, React Flow service dependency and workflow DAG graphs, distributed trace Gantt waterfalls, microservice health drilldowns, and live chaos injection controls.

### 1. Architectural Decisions
1. **100% Backend API Fidelity**: Consumes the existing FastAPI endpoints directly via Vite proxy (`/api -> http://localhost:8000`), with zero mock schemas or redundant state stores.
2. **On-Demand Data Fetching**: Prohibits continuous background polling; uses on-demand view loading, explicit user refresh actions, and post-mutation invalidation.
3. **GPU-Accelerated Graph Visualizations**: Adopted `@xyflow/react` (React Flow) for rendering the 12-node service dependency topology graph and workflow DAGs with custom HTML nodes, edge type color-coding, and interactive inspector drawers.
4. **Zero-Dependency Trace Gantt Waterfall**: Implemented a custom pure SVG/CSS flex Gantt chart for sub-millisecond timeline rendering of hierarchical parent-child spans without heavy charting bundle overhead.
5. **RFC 7807 Error Integration**: Typed fetch client (`frontend/src/api/client.ts`) intercepts Problem Details error shapes (`{ title, status, detail, error_code, invalid_params }`) and surfaces user-friendly alerts with retry actions.

### 2. Components Implemented

#### Typed API Client & Domain Models (`frontend/src/`)
* `types/`: `api.ts`, `service.ts`, `workflow.ts`, `execution.ts`, `incident.ts`, `simulator.ts` matching backend Pydantic schemas.
* `api/`: `client.ts`, `services.ts`, `workflows.ts`, `executions.ts`, `incidents.ts`, `simulator.ts`.

#### Reusable UI & Visualizer Components (`frontend/src/components/`)
* `common/`: `Header.tsx` (navigation tabs & live API pulse), `StatCard.tsx`, `Badge.tsx`, `LoadingSkeleton.tsx`, `ErrorAlert.tsx`, `EmptyState.tsx`.
* `graphs/`: `TopologyGraph.tsx` (React Flow service topology), `WorkflowDag.tsx` (React Flow step graph).
* `waterfall/`: `TraceWaterfall.tsx` (Gantt waterfall with collapsible spans), `SpanDetailDrawer.tsx` (slide-out span inspector).

#### Core Dashboard Views (`frontend/src/views/`)
* `OverviewView.tsx`: System-wide telemetry KPIs, service health summary table, active chaos incidents feed, and recent executions.
* `TopologyView.tsx`: Interactive service dependency map with clickable Service Inspector drawer and live tuning configuration editor (`PUT /api/v1/services/{name}`).
* `WorkflowsView.tsx`: Workflow selector, DAG visualizer, duration distribution metrics (P50/P95), and workflow execution feed.
* `ExecutionsView.tsx`: Multi-column execution search (status, incident toggle, duration), execution metadata, and hierarchical Trace Gantt Waterfall visualizer.
* `ServicesView.tsx`: Microservice registry, database-side latency percentiles (P50..P99), reliability breakdown, and live concurrency tuning form.
* `SimulatorView.tsx`: 7 causal chaos scenario catalog cards, synthetic trace generator, targeted chaos injection workbench, and real-time execution results banner.

### 3. Verification & Quality Results

* **TypeScript Compilation**: Clean (`npm run type-check` / `tsc --noEmit` -> **0 errors**).
* **Production Build**: Clean bundle in **3.28s** (`npm run build` / `vite build`).
* **Backend Regression Suite**: **48 / 48 tests passing** in **3.02s** (`pytest -p no:cacheprovider tests/ -v`).
* **Backend Static Analysis**: **0 errors** across 75 source files (Mypy) / 94 files (Ruff).

---

## Milestone 5: Event Streaming with Kafka

* **Status**: Completed
* **Branch**: `feat/kafka-event-streaming`
* **Objective**: Decouple synthetic trace generation from database persistence by implementing an asynchronous event streaming architecture using Apache Kafka in KRaft mode, micro-batched TimescaleDB ingestion workers, and dual-mode testing buses.

### 1. Architectural Decisions
1. **KRaft Mode Deployment**: Deployed Apache Kafka 3.7.0 without Zookeeper, reducing operational overhead, memory consumption, and startup latency.
2. **Asyncio-Native Client**: Selected `aiokafka>=0.11.0` for non-blocking asynchronous event production and consumption integrated with the FastAPI event loop.
3. **Partition Key Affinity (`execution_id`)**: All trace events are produced with `key = event.execution_id.encode('utf-8')`, guaranteeing all spans for a given workflow execution land on the same Kafka partition for strict FIFO causal ordering.
4. **Dual-Mode Event Bus**: Implemented `InMemoryEventBus` alongside `KafkaTraceEventProducer`/`Consumer` to guarantee 100% hermetic CI/CD unit testing without requiring an active external broker.
5. **Micro-Batching Ingestion Worker**: Implemented `StreamingIngestor` (`apps/worker/stream_ingestor.py`) buffering incoming records ($1,000$ events / $50\text{ms}$ flush window), executing bulk `insert(TraceEventModel)` with merge fallback for strict idempotency.
6. **Offset Commit Invariant**: Manual offset commit (`consumer.commit()`) occurs strictly *after* successful database transaction commit, guaranteeing at-least-once delivery without data loss.

### 2. Components Implemented

#### Event Bus & Serializers (`packages/events/`)
* `serializers.py`: `JsonTraceEventSerializer` with ISO 8601 UTC microsecond precision and Pydantic v2 validation.
* `producer.py`: `AsyncTraceEventProducer` protocol, `KafkaTraceEventProducer` (aiokafka), `InMemoryTraceEventProducer`.
* `consumer.py`: `AsyncTraceEventConsumer` protocol, `KafkaTraceEventConsumer` (aiokafka manual commit), `InMemoryTraceEventConsumer`.
* `bus.py`: `InMemoryEventBus`, `create_producer()`, `create_consumer()` factory abstractions.

#### Background Ingestion Worker (`apps/worker/`)
* `stream_ingestor.py`: Standalone worker daemon consuming from `tracemind.events.raw` using group `tracemind-ingestor`, micro-batching, and signal trapping (`SIGINT`, `SIGTERM`).

#### Real-Time Simulator Streaming (`apps/simulator/`)
* `streaming.py`: `StreamingTraceSimulator` emitting canonical `TraceEvent` objects live as discrete-event execution progresses.

#### REST API & Frontend Integrations
* `apps/api/schemas/simulator.py`: Added `stream_to_kafka: bool = False` to `SimulationGenerateRequest` and `streamed_to_kafka: bool` to `SimulationGenerateResponse`.
* `apps/api/routes/simulator.py`: Streaming trace generation branch with RFC 7807 error handling.
* `frontend/src/views/SimulatorView.tsx`: Added "Stream to Kafka" toggle and execution result indicators.
* `docker-compose.yml`: Added `kafka` (KRaft mode) and `worker` services.

### 3. Verification & Performance Benchmark Results

```text
================================================================================
                TraceMind Milestone 5 Streaming Pipeline Benchmark             
================================================================================
 Total Benchmark Events Processed   : 25,000 spans
 Micro-Batch Buffer Limit           : 1,000 events / batch
--------------------------------------------------------------------------------
 1. Producer Stream Ingestion Rate  : 287,472 events/sec (0.087s)
 2. Consumer & DB Persistence Rate  : 27,563 events/sec (0.907s)
 3. End-to-End Pipeline Throughput  : 25,151 events/sec (0.994s)
 4. Simulator Live Stream Rate      : 83,820 events/sec (3,835 spans in 0.046s)
--------------------------------------------------------------------------------
 Micro-Batch Flush Latencies (per 1,000-event batch):
   • P50 Flush Latency              : 24.00 ms
   • P95 Flush Latency              : 49.02 ms
   • P99 Flush Latency              : 73.81 ms
   • Mean Flush Latency             : 27.67 ms
================================================================================
 Target Throughput Criteria (>5,000 events/sec) : [PASSED] (5.5x margin)
================================================================================
```

* **Test Suite**: **57/57 tests passing** in **4.33s** (`pytest -p no:cacheprovider tests/ -v`).
* **Type Safety**: **Mypy clean (0 errors)** across 80 source files.
* **Linter & Formatter**: **Ruff clean** across 99 source files.
* **Frontend Checks**: **TypeScript type-check 0 errors**, **Vite build passing in 3.02s**.

---

## Milestone 6: ML Failure & Latency Prediction Engine with TreeSHAP Explainability

* **Status**: Completed
* **Branch**: `feat/ml-prediction-engine`
* **Objective**: Build an in-flight temporal feature extraction pipeline, calibrated XGBoost failure classifier, continuous latency regressor, exact TreeSHAP feature attribution engine with diagnostic explainability, database persistence layer, REST endpoints, and interactive frontend risk visualizers.

### 1. Architectural Decisions
1. **Strict Temporal Integrity ($t \le t_k$)**: In-flight feature extraction prunes all spans where $t > t_k$, preventing future temporal leakage during inference.
2. **Canonical 16-Dimensional Tabular Feature Space**: Computes step count, elapsed duration, cumulative retries, intermediate errors, mean/max/last step latencies, cache miss/database query flags, per-service cumulative durations (`auth`, `customer`, `inventory`, `pricing`, `payment`), and latency ratios vs nominal baselines.
3. **Calibrated Gradient-Boosted Classifiers**: XGBoost binary classifier with positive-class reweighting (`scale_pos_weight`) predicting failure probability and mapping to categorical risk bands (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
4. **Duration Forecasting Regression**: XGBoost regressor predicting continuous total workflow execution duration in milliseconds.
5. **Exact TreeSHAP Explainability**: Integrates `shap.TreeExplainer` on tree ensembles to compute exact additive local Shapley attributions $\phi_0 + \sum \phi_i(x) = f(x)$ with human-readable diagnostic messages.
6. **Thread-Safe Model Registry & Cache**: Singleton `ModelRegistry` with disk persistence, joblib serialization, and automatic bootstrap training on synthetic trace simulations if no models exist on disk.
7. **Database Persistence Layer**: `PredictionModel` SQLAlchemy ORM entity in `workflow_predictions` table and async `PredictionRepository` providing chronological prediction history per execution and high-risk filtering.
8. **Interactive TreeSHAP Frontend Drawer**: Slide-out drawer in `ExecutionsView.tsx` with diverging red/green horizontal attribution bar charts and risk badges.

### 2. New & Modified Components

#### Machine Learning Engine (`apps/ml/`)
* `features.py`: `TraceFeatureExtractor` with 16 canonical features and prefix dataset generator.
* `models.py`: `WorkflowFailureClassifier` and `WorkflowLatencyRegressor` model wrappers.
* `trainer.py`: `ModelTrainer` with synthetic balanced dataset generation and metric evaluation.
* `explainability.py`: `TreeSHAPExplainer` computing exact Shapley values and diagnostic text.
* `registry.py`: `ModelRegistry` managing model serialization, versioning, and caching.

#### Persistence Layer (`packages/database/`)
* `models/prediction.py`: `PredictionModel` ORM entity with JSON feature vectors and SHAP attributions.
* `repositories/prediction_repository.py`: Async repository for saving and querying prediction records.

#### REST API Layer (`apps/api/`)
* `schemas/prediction.py`: `PredictionRequest`, `PredictionResponse`, `FeatureContributionResponse`, `TrainRequest`, `TrainResponse`, `ModelMetadataResponse`.
* `routes/predictions.py`: REST endpoints mounted under `/api/v1/predictions`.
* `main.py`: Mounted `predictions_router` and updated OpenAPI metadata to version `0.6.0`.

#### Frontend Dashboard (`frontend/src/`)
* `types/prediction.ts`: TypeScript interfaces for predictions, SHAP attributions, and training requests.
* `api/predictions.ts`: Typed API client for `/api/v1/predictions`.
* `components/waterfall/ShapAttributionDrawer.tsx`: Slide-out TreeSHAP drawer with diverging bar visualizer.
* `views/ExecutionsView.tsx`: Integrated ML risk level badges, forecast duration, and TreeSHAP drawer trigger.

#### Test Suite & Benchmarks
* `tests/unit/test_feature_extraction.py`: Temporal integrity, prefix slicing, and feature calculation tests.
* `tests/unit/test_ml_models.py`: Classifier, regressor, and trainer pipeline tests.
* `tests/unit/test_explainability.py`: TreeSHAP attribution ranking and diagnostic description tests.
* `tests/integration/test_api_predictions.py`: End-to-end integration tests for `/api/v1/predictions`.
* `benchmarks/benchmark_ml_inference.py`: Throughput and P99 latency benchmark.

### 3. Verification & Performance Benchmark Results

```text
================================================================================
        TraceMind Milestone 6 ML & TreeSHAP Inference Benchmark        
================================================================================
 Total Benchmark Inferences Processed : 1,000 runs
--------------------------------------------------------------------------------
 1. Feature Extraction Throughput      : 37,414 extractions/sec (0.027s)
 2. End-to-End Inference Throughput    : 356 inferences/sec (2.808s)
--------------------------------------------------------------------------------
 Single-Sample End-to-End Latency (Feature Extractor + XGBoost + TreeSHAP):
   • P50 Latency                       : 2.65 ms
   • P90 Latency                       : 3.57 ms
   • P95 Latency                       : 3.92 ms
   • P99 Latency                       : 4.37 ms
   • Mean Latency                      : 2.81 ms
================================================================================
 Target Latency Criteria (P99 < 15.0ms) : [PASSED]
================================================================================
```

* **Test Suite**: **68/68 tests passing** in **6.16s** (`pytest -p no:cacheprovider tests/ -v`).
* **Type Safety**: **Mypy clean (0 errors)** across 97 source files.
* **Linter & Formatter**: **Ruff clean** across 120 source files.
* **Frontend Checks**: **TypeScript type-check 0 errors**, **Vite build passing in 3.96s**.

