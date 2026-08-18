# Milestone 4 Implementation Plan: Interactive Frontend Dashboard

> **TraceMind — AI-Powered Distributed Workflow Intelligence Platform**  
> **Status:** PROPOSED & AWAITING APPROVAL  
> **Target Branch:** `feat/frontend-dashboard`  
> **Source of Truth:** Monorepo architecture, FastAPI OpenAPI specification, and Pydantic v2 domain schemas.

---

## 1. Context & Foundation (Milestones 0–3 Summary)

Milestone 4 builds directly upon the stable foundation established in Milestones 0, 1, 2, and 3:

* **Milestone 0 (Repository Foundation)**:
  * Monorepo layout with Python 3.12 (`uv`), FastAPI, and React 18 (`TypeScript + Vite + Tailwind CSS`).
  * Domain models (`packages/domain/`), Docker setup, and CI/CD pipelines.
* **Milestone 1 (TraceSim Discrete-Event Simulator)**:
  * Deterministic simulation of 7 business microservices (`auth-service`, `customer-service`, `inventory-service`, `pricing-service`, `payment-service`, `order-service`, `notification-service`) and 5 infrastructure components (`customer-cache`, `customer-db`, `inventory-db`, `payment-gateway`, `api-gateway`).
  * 7 causal chaos scenario presets, ground-truth incident generation, and reproducible pseudo-random seed generation.
* **Milestone 2 (Persistence & Query Engine)**:
  * PostgreSQL + TimescaleDB storage with `trace_events` hypertable partitioned on `timestamp` with composite primary key `(event_id, timestamp)`.
  * Async repositories (`WorkflowRepository`, `ServiceRepository`, `TraceEventRepository`, `IncidentRepository`), bulk chunked ingestion, single-pass database-side telemetry aggregation, and linear $\mathcal{O}(N)$ DAG trace tree reconstruction.
* **Milestone 3 (FastAPI Core Endpoints & Simulation Control APIs)**:
  * Production-grade RESTful API layer with Pydantic v2 schemas (`apps/api/schemas/`), RFC 7807 Problem Details error handling (`apps/api/exceptions.py`), and 48 passing unit/integration tests in 3.00s.
  * Direct in-memory simulation ingestion (`DatasetIngestor.ingest_simulation_result`).

---

## 2. Milestone 4 Objective

Transform TraceMind from a backend engine into a rich, interactive **Developer Observability & Workflow Intelligence Dashboard**.

The dashboard enables engineers to:
1. **Monitor System Health**: View system-wide throughput, success/error rates, active incidents, and service health summaries.
2. **Explore Service Topology**: Interact with a live service dependency graph visualizer showing microservices, infrastructure nodes, and directed dependency edges.
3. **Inspect Workflow DAGs**: Browse workflow definitions, inspect topological steps/weights, and review execution duration distributions.
4. **Analyze Distributed Traces**: Search executions with multi-column filters and drill into hierarchical parent-child DAG trace trees and Gantt waterfall timelines.
5. **Observe Microservices**: Drill into per-service latency percentiles (P50..P99), reliability rates, timeout counts, and live capacity configurations.
6. **Simulate Chaos Scenarios**: Explore the 7 causal chaos scenario catalog, trigger deterministic synthetic workloads, and inject targeted chaos experiments.

---

## 3. Frontend Architecture

### 3.1 Directory Structure

```text
frontend/src/
├── api/                        # Typed REST API Client Layer
│    ├── client.ts              # Core fetch client with RFC 7807 error handling
│    ├── services.ts            # Service catalog, latency percentiles & topology API
│    ├── workflows.ts           # Workflow definitions, DAGs & stats API
│    ├── executions.ts          # Execution search, event streams & trace tree API
│    ├── incidents.ts           # Incident query API
│    └── simulator.ts           # Simulation generation & chaos injection API
├── types/                      # TypeScript definitions matching Backend Pydantic Schemas
│    ├── api.ts                 # PaginationMeta, PaginatedResponse, ApiError
│    ├── service.ts             # ServiceProfile, ServiceTopology, ServiceHealth
│    ├── workflow.ts            # WorkflowNode, WorkflowEdge, WorkflowDefinition, WorkflowStats
│    ├── execution.ts           # ExecutionSummary, TraceEvent, TraceTreeNode
│    ├── incident.ts            # IncidentResponse, IncidentTraceResponse
│    └── simulator.ts           # ChaosScenarioInfo, SimulationRequest, ChaosRequest
├── components/                 # Reusable UI & Visualizer Components
│    ├── common/                # Header, StatCard, Badge, LoadingSkeleton, ErrorAlert, Modal
│    ├── graphs/                # TopologyGraph (React Flow), WorkflowDag (React Flow)
│    ├── waterfall/             # TraceWaterfall, SpanRow, SpanDetailDrawer
│    └── forms/                 # ChaosInjectionModal, SimulationGenerateModal
├── views/                      # 6 Core Dashboard Views
│    ├── OverviewView.tsx       # System KPIs, active incidents, recent executions
│    ├── TopologyView.tsx       # Interactive Service Dependency Graph & Service Inspector
│    ├── WorkflowsView.tsx      # Workflow DAG Explorer, execution list, duration stats
│    ├── ExecutionsView.tsx     # Trace Explorer, multi-column search & Waterfall Gantt
│    ├── ServicesView.tsx       # Service Observability, latency percentiles, error rates
│    └── SimulatorView.tsx      # Chaos Scenario Catalog & Live Simulation Controls
├── App.tsx                     # Main Dashboard Shell with View Switcher & Notification State
├── main.tsx                    # React Entry point
└── index.css                   # Tailwind CSS styling & custom dark-theme scrollbars
```

### 3.2 Graph & Visualization Libraries
* **Service Topology & Workflow DAG**: `@xyflow/react` (the official React Flow package) for fluid, GPU-accelerated node/edge drag-and-drop, zoom/pan canvas, and custom styled nodes.
* **Distributed Trace Waterfall**: Custom pure SVG/CSS flex Gantt chart with millisecond time scales, service-colored span bars, and collapsible nested children for sub-millisecond rendering performance without bundle bloat.
* **Icons**: `lucide-react` (already present in `package.json`).

---

## 4. Detailed View Specifications & API Contracts

### View 1: System Overview (`OverviewView.tsx`)
* **Purpose**: Single-pane operational cockpit showing aggregate telemetry, health KPIs, active incidents, and recent executions.
* **API Endpoints**:
  * `GET /api/v1/services/telemetry/summary` -> Computes total events, error rate %, avg latency ms, retry count across all services.
  * `GET /api/v1/incidents?limit=5` -> Displays recent/active chaos incidents.
  * `GET /api/v1/executions?limit=10` -> Displays recent execution feed.
* **Components**:
  * 5 KPI cards (Total Workflows, System Throughput, Error Rate %, P95 Latency ms, Active Incidents).
  * System Health Summary table listing all microservices with health badges (`HEALTHY`, `DEGRADED`, `CRITICAL`).
  * Recent executions list with status chips and duration metrics.

### View 2: Service Dependency Topology (`TopologyView.tsx`)
* **Purpose**: Visual dependency map of the distributed architecture.
* **API Endpoints**:
  * `GET /api/v1/services/topology` -> Returns `{ nodes: TopologyNode[], edges: TopologyEdge[] }`.
  * `GET /api/v1/services/{service_name}` -> Fetches selected service profile.
  * `PUT /api/v1/services/{service_name}` -> Updates capacity, timeouts, and retries.
* **Components**:
  * React Flow canvas with custom nodes color-coded by type (`business_microservice` vs `infrastructure_*`).
  * Edge labels indicating relationship (`HTTP_RPC`, `CACHE_LOOKUP`, `DB_QUERY`, `GATEWAY_CALL`).
  * Interactive Service Inspector drawer on node click showing latency percentiles and configuration editor.

### View 3: Workflow DAG Explorer (`WorkflowsView.tsx`)
* **Purpose**: Inspect registered workflow DAG topologies and performance characteristics.
* **API Endpoints**:
  * `GET /api/v1/workflows` -> List workflow definitions.
  * `GET /api/v1/workflows/{id}` -> Get workflow definition details (`nodes`, `edges`).
  * `GET /api/v1/workflows/{id}/stats` -> Aggregate duration percentiles (P50/P95) and error rate.
  * `GET /api/v1/workflows/{id}/executions?limit=10` -> List executions for the workflow.
* **Components**:
  * Workflow selector dropdown.
  * React Flow DAG renderer displaying step sequence, service assignment, and routing conditions.
  * Workflow KPI panel (P50 duration, P95 duration, failure rate %, total runs).
  * Paginated table of executions for the selected workflow.

### View 4: Execution & Trace Waterfall Viewer (`ExecutionsView.tsx`)
* **Purpose**: Deep-dive trace analysis and span lifecycle debugging.
* **API Endpoints**:
  * `GET /api/v1/executions` (with query params `page`, `limit`, `status`, `incident_id`, `is_incident_affected`, `min_duration_ms`, `max_duration_ms`).
  * `GET /api/v1/executions/{id}` -> Single execution summary.
  * `GET /api/v1/executions/{id}/tree` -> Hierarchical parent-child DAG trace tree.
  * `GET /api/v1/executions/{id}/events` -> Chronological span event stream.
* **Components**:
  * Search and filter toolbar (Status filter, Incident toggle, Duration range, Time window).
  * Paginated execution data table.
  * Hierarchical Trace Tree & Gantt Waterfall Visualizer:
    * Timeline axis calibrated from `started_at` to `completed_at`.
    * Indented span rows showing `service`, `operation`, `status`, and duration bar.
    * Error indicators for failed/timeout spans (`SPAN_ERROR`, `SPAN_TIMEOUT`, `RETRY_ATTEMPT`).
    * Clickable span drawer displaying correlation ID, parent ID, and span metadata.

### View 5: Service Observability (`ServicesView.tsx`)
* **Purpose**: Microservice performance metrics and latency percentile breakdown.
* **API Endpoints**:
  * `GET /api/v1/services` -> Service list.
  * `GET /api/v1/services/{name}/latency` -> Percentiles (`min`, `mean`, `median_p50`, `p90`, `p95`, `p99`, `max`).
  * `GET /api/v1/services/{name}/health` -> Reliability rates (`total_events`, `failure_rate_percent`, `retry_rate_percent`, `timeout_rate_percent`).
  * `PUT /api/v1/services/{name}` -> Update capacity, retries, and baseline parameters.
* **Components**:
  * Service navigation grid.
  * Latency distribution card (P50/P90/P95/P99 latency histogram/bars).
  * Reliability breakdown card (Call volume, error rate, retry rate, timeout count).
  * Configuration editor modal with immediate persistence.

### View 6: Chaos & Simulation Control Console (`SimulatorView.tsx`)
* **Purpose**: Synthetic telemetry generation and live chaos injection workbench.
* **API Endpoints**:
  * `GET /api/v1/simulator/scenarios` -> Catalog of 7 supported causal chaos incident presets.
  * `POST /api/v1/simulator/generate` -> Trigger synthetic simulation run.
  * `POST /api/v1/simulator/inject-chaos` -> Trigger targeted chaos scenario experiment.
* **Components**:
  * Scenario Catalog Cards displaying name, description, severity, affected services, and ground-truth root cause.
  * **Targeted Chaos Injection Panel**: Select scenario, workflow count ($10..1,000$), arrival rate, random seed, DB persistence toggle, and "Inject Chaos" button.
  * **Synthetic Trace Generator Panel**: Generate baseline or customized workloads with seed determinism.
  * Execution feedback banner displaying generation wall time, affected executions count, error rate %, and button to view generated traces in Execution Explorer.

---

## 5. Error Handling & UX Design Standards

1. **RFC 7807 Error Integration**: The API client automatically intercepts RFC 7807 error responses (`{ title, status, detail, error_code, invalid_params }`) and renders descriptive alerts.
2. **Loading & Empty States**:
   * Loading skeletons with pulsing dark-mode placeholders during data fetching.
   * Informative empty states with actionable suggestions (e.g., "No executions found matching filter. Generate a simulation to populate data.").
3. **Dark Theme Aesthetics**:
   * Rich slate palette (`bg-slate-950`, `surface-900`, `surface-800`), crisp emerald accents (`text-emerald-400`, `bg-emerald-500/10`), amber warnings, and rose error states.
   * JetBrains Mono / Fira Code monospace typography for IDs, timestamps, and latency numbers.
4. **Zero Continuous Polling**: Dashboard uses on-demand data fetching with manual refresh buttons and post-action invalidation triggers (e.g. refreshing Overview upon running a simulation).

---

## 6. Testing & Verification Strategy

1. **Frontend Type Check**:
   ```bash
   cd frontend
   npm run type-check   # tsc --noEmit
   ```
2. **Frontend Build**:
   ```bash
   cd frontend
   npm run build        # tsc && vite build
   ```
3. **Backend Full Regression Suite**:
   ```bash
   .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/ -v  # 48/48 tests passing
   .\.venv\Scripts\ruff.exe check .
   .\.venv\Scripts\python.exe -m mypy packages apps tests
   ```
4. **End-to-End Visual Smoke Test**:
   * Start backend (`uvicorn apps.api.main:app`) and frontend dev server (`npm run dev`).
   * Verify all 6 views render live data from the backend without console errors.

---

## 7. Implementation Sequence

1. **Step 1 — Dependencies & Types**:
   * Add `@xyflow/react` to `frontend/package.json`.
   * Create `frontend/src/types/` (`api.ts`, `service.ts`, `workflow.ts`, `execution.ts`, `incident.ts`, `simulator.ts`).
2. **Step 2 — API Client Layer**:
   * Implement `frontend/src/api/client.ts` and modular clients (`services.ts`, `workflows.ts`, `executions.ts`, `incidents.ts`, `simulator.ts`).
3. **Step 3 — Reusable UI Components**:
   * Create `StatCard.tsx`, `Badge.tsx`, `LoadingSkeleton.tsx`, `ErrorAlert.tsx`, and navigation header.
4. **Step 4 — Graph & Visualizer Components**:
   * Create `TopologyGraph.tsx` and `WorkflowDag.tsx` using `@xyflow/react`.
   * Create `TraceWaterfall.tsx` for distributed trace timeline rendering.
5. **Step 5 — Dashboard Views**:
   * Implement `OverviewView.tsx`, `TopologyView.tsx`, `WorkflowsView.tsx`, `ExecutionsView.tsx`, `ServicesView.tsx`, `SimulatorView.tsx`.
6. **Step 6 — Main App Integration & Verification**:
   * Wire views and navigation into `App.tsx`.
   * Run type-checks, build, and test suite.
7. **Step 7 — Documentation & Commit**:
   * Create `docs/architecture/frontend.md`.
   * Update `docs/roadmap.md`, `docs/architecture/overview.md`, and `docs/project-history.md`.
   * Commit with conventional commit boundaries and push branch.
