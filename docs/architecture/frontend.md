# TraceMind Frontend Architecture & Dashboard Documentation

> **Module H — Interactive Developer Observability & Workflow Intelligence Dashboard**  
> **Milestone 4 Reference Architecture**

---

## 1. System Philosophy & Objectives

The TraceMind Frontend is an interactive **Developer Observability & Workflow Intelligence Dashboard** built to bridge distributed trace execution graphs, microservice dependencies, live chaos injection, and performance telemetry into a single-pane engineering interface.

Key architectural goals:
1. **100% Backend API Fidelity**: Consumes the existing FastAPI endpoints without mock layers or duplicate business logic.
2. **Zero Polling Overhead**: Operates on-demand with explicit user refresh actions and post-mutation cache invalidation.
3. **Sub-Millisecond Visualization Performance**: Renders hierarchical parent-child DAG trace trees and Gantt waterfall timelines with zero UI jank using pure SVG/CSS flex layouts.
4. **Interactive Graph Topologies**: Visualizes service dependencies and workflow DAGs using `@xyflow/react` (React Flow) with custom nodes and directed relationship edges.
5. **Standardized RFC 7807 Error Handling**: Gracefully transforms backend Problem Details into actionable, user-friendly error banners with retry capabilities.

---

## 2. Directory Structure

```text
frontend/src/
├── api/                        # Typed REST API Client Layer
│    ├── client.ts              # Core fetch client with RFC 7807 Problem Details error parsing
│    ├── services.ts            # Service catalog, latency percentiles & topology API
│    ├── workflows.ts           # Workflow definitions, DAGs & stats API
│    ├── executions.ts          # Execution search, event streams & trace tree API
│    ├── incidents.ts           # Incident history API
│    └── simulator.ts           # Simulation generation & chaos injection API
├── types/                      # TypeScript definitions matching Backend Pydantic Schemas
│    ├── api.ts                 # PaginationMeta, PaginatedResponse, ApiError
│    ├── service.ts             # ServiceProfile, ServiceTopology, ServiceHealth
│    ├── workflow.ts            # WorkflowNode, WorkflowEdge, WorkflowDefinition, WorkflowStats
│    ├── execution.ts           # ExecutionSummary, TraceEvent, TraceTreeNode
│    ├── incident.ts            # IncidentResponse, IncidentTraceResponse
│    └── simulator.ts           # ChaosScenarioInfo, SimulationRequest, ChaosRequest
├── components/                 # Reusable UI & Visualizer Components
│    ├── common/                # Header, StatCard, Badge, LoadingSkeleton, ErrorAlert, EmptyState
│    ├── graphs/                # TopologyGraph (React Flow), WorkflowDag (React Flow)
│    └── waterfall/             # TraceWaterfall, SpanDetailDrawer
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

---

## 3. Core Dashboard Views & API Integrations

### View 1: System Overview (`OverviewView.tsx`)
* **Purpose**: Single-pane operational cockpit showing aggregate telemetry, health KPIs, active incidents, and recent executions.
* **Backend Integrations**:
  * `GET /api/v1/services/telemetry/summary`: Single-pass database-side aggregation of service throughput, failure rates, and P95 latency.
  * `GET /api/v1/incidents`: Historical chaos incident records.
  * `GET /api/v1/executions?limit=10`: Recent execution feed.
* **Features**:
  * 5 KPI cards (Total Trace Events, Avg Error Rate %, Mean Latency ms, Max P95 Latency ms, Recorded Incidents).
  * Microservice Health Summary table with health badges (`HEALTHY`, `DEGRADED`, `CRITICAL`).
  * Quick drill-down navigation to Topology, Services, and Executions views.

### View 2: Service Dependency Topology (`TopologyView.tsx`)
* **Purpose**: Interactive dependency map of the distributed architecture.
* **Backend Integrations**:
  * `GET /api/v1/services/topology`: Returns nodes and directed edges.
  * `GET /api/v1/services/{name}`: Service profile metadata.
  * `GET /api/v1/services/{name}/latency`: Percentiles (P50, P90, P95, P99).
  * `GET /api/v1/services/{name}/health`: Reliability metrics.
  * `PUT /api/v1/services/{name}`: Live concurrency capacity, timeout, and retry tuning.
* **Features**:
  * React Flow canvas with custom nodes color-coded by type (`business_microservice` vs `infrastructure_*`).
  * Edge labels indicating relationship (`HTTP_RPC`, `CACHE_LOOKUP`, `DB_QUERY`, `GATEWAY_CALL`).
  * Interactive Service Inspector drawer with live configuration update form.

### View 3: Workflow DAG Explorer (`WorkflowsView.tsx`)
* **Purpose**: Topological workflow step inspection and runtime duration distributions.
* **Backend Integrations**:
  * `GET /api/v1/workflows`: Registered workflow definitions.
  * `GET /api/v1/workflows/{id}`: Step nodes and transitions.
  * `GET /api/v1/workflows/{id}/stats`: Aggregate duration statistics.
  * `GET /api/v1/workflows/{id}/executions`: Paginated list of executions.
* **Features**:
  * Workflow selector dropdown.
  * React Flow step visualizer with operation labels and transition weights.
  * Duration KPI cards (P50 duration, P95 duration, success rate %, total runs).
  * Paginated table with click-through navigation to trace waterfalls.

### View 4: Execution & Trace Waterfall Viewer (`ExecutionsView.tsx`)
* **Purpose**: Deep-dive trace analysis and span lifecycle debugging.
* **Backend Integrations**:
  * `GET /api/v1/executions`: Multi-column filtered search (`status`, `workflow_id`, `is_incident_affected`, pagination).
  * `GET /api/v1/executions/{id}`: Execution details and root cause.
  * `GET /api/v1/executions/{id}/tree`: Hierarchical parent-child DAG trace tree.
* **Features**:
  * Execution filter toolbar with status chips and incident toggles.
  * Hierarchical Trace Tree & Gantt Waterfall Visualizer:
    * Relative timeline offset from execution start.
    * Service-colored span bars indicating duration in milliseconds.
    * Error badges for failed spans (`SPAN_ERROR`, `SPAN_TIMEOUT`, `RETRY_ATTEMPT`).
    * Clickable span drawer displaying correlation ID, parent ID, and span metadata.

### View 5: Service Observability (`ServicesView.tsx`)
* **Purpose**: Microservice performance metrics and latency percentile breakdown.
* **Backend Integrations**:
  * `GET /api/v1/services`: Service list.
  * `GET /api/v1/services/{name}/latency`: Database-side percentiles (Min, P50, P90, P95, P99, Max).
  * `GET /api/v1/services/{name}/health`: Reliability metrics.
  * `PUT /api/v1/services/{name}`: Update capacity, timeout, retries, and baseline parameters.
* **Features**:
  * Service registry sidebar.
  * Latency distribution card with percentile breakdown.
  * Reliability breakdown card with failure, timeout, and retry rates.
  * Live configuration tuning form with immediate database persistence.

### View 6: Chaos & Simulation Control Console (`SimulatorView.tsx`)
* **Purpose**: Synthetic telemetry generation and live chaos injection workbench.
* **Backend Integrations**:
  * `GET /api/v1/simulator/scenarios`: Catalog of 7 supported causal chaos incident presets.
  * `POST /api/v1/simulator/generate`: Trigger synthetic simulation run.
  * `POST /api/v1/simulator/inject-chaos`: Trigger targeted chaos scenario experiment.
* **Features**:
  * Scenario catalog cards with severity badge, affected services, and ground-truth root cause.
  * **Synthetic Trace Generator Panel**: Generate customizable workloads with seed determinism.
  * **Targeted Chaos Injection Panel**: Select scenario, workload count, arrival rate, random seed, and trigger live injection.
  * Live execution results banner with quick navigation to view generated traces.

---

## 4. UI Design System & UX Standards

* **Aesthetic**: Polished dark developer-observability theme.
* **Palette**:
  * Backgrounds: `bg-slate-950`, `bg-slate-900/60`, `bg-slate-950/70`.
  * Accents: Emerald (`#10b981`) for healthy/success, Amber (`#f59e0b`) for warnings/degraded, Rose (`#f43f5e`) for errors/incidents, Sky (`#0284c7`) for gateways/information, Purple (`#a855f7`) for caches.
* **Typography**: Monospace (`JetBrains Mono`, `Fira Code`) for IDs, timestamps, latencies, and technical values; `Inter` for prose.
* **States**:
  * Loading skeletons with pulsing dark-mode placeholders.
  * RFC 7807 Error Alert banners with retry buttons.
  * Informative empty states with actionable suggestions.
