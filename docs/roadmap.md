# TraceMind Engineering Roadmap

This document outlines the phased milestone execution plan for TraceMind.

---

## Milestone 0: Repository Foundation & Core Architecture
* **Objective**: Scaffold repository structure, Python/Node toolchains, CI/CD, documentation, and base domain schemas.
* **Deliverables**:
  - Monorepo folder hierarchy (`apps/`, `packages/`, `frontend/`, `docs/`, `tests/`).
  - Python 3.12 `pyproject.toml` with dependencies and dev tools (Ruff, Mypy, Pytest).
  - Pydantic domain models for traces, services, workflows, incidents, predictions.
  - FastAPI application skeleton with health check.
  - React/TypeScript/Vite frontend dashboard skeleton.
  - GitHub Actions CI pipeline.
* **Status**: Completed

---

## Milestone 1: TraceSim — Synthetic Distributed System Simulator
* **Objective**: Build a deterministic discrete-event simulator generating multi-service workflow traces.
* **Deliverables**:
  - Discrete-event execution engine with configurable services (`auth`, `customer`, `database`, `inventory`, `pricing`, `payment`, `order`, `notification`).
  - Heavy-tailed Log-Normal / Gamma latency distributions with natural tail spikes, capacity/queueing delays, retries, and client timeouts.
  - Causal chaos scenarios (`TRAFFIC_SPIKE`, `DATABASE_LATENCY`, `PAYMENT_LATENCY_DEGRADATION`, `SERVICE_FAILURE`, `NETWORK_LATENCY`, `RETRY_STORM`, `CASCADING_FAILURE`).
  - Preserved ground-truth metadata in canonical `Incident` entities.
  - Streaming export to JSONL and Parquet formats (`executions`, `events`, `incidents`).
  - Comprehensive statistical summaries and CLI tool (`python -m apps.simulator`).
* **Status**: Completed

---

## Milestone 2: Persistence & Query Engine
* **Objective**: Implement PostgreSQL & TimescaleDB storage with SQLAlchemy and Alembic.
* **Deliverables**:
  - PostgreSQL & TimescaleDB hypertable schema (`trace_events` partitioned on `timestamp`, `services`, `workflow_definitions`, `workflow_executions`, `incidents`).
  - Alembic migrations (`001_initial_persistence_schema.py`) with TimescaleDB hypertable initialization and composite index optimizations.
  - Async repository layer (`ServiceRepository`, `WorkflowRepository`, `TraceEventRepository`, `IncidentRepository`) with database-side `percentile_cont` latency aggregation and linear-time DAG trace tree reconstruction.
  - High-throughput chunked bulk ingestion pipeline (`DatasetIngestor`) supporting Parquet & JSONL formats with idempotency guarantees.
  - FastAPI query routes under `/api/v1/traces`, `/api/v1/services`, `/api/v1/incidents`.
* **Status**: Completed

---

## Milestone 3: FastAPI Core Endpoints & Simulation Control APIs
* **Objective**: Expose complete RESTful API for workflow topology, execution querying, service health & dependency graphs, and live simulation controls.
* **Deliverables**:
  - `/api/v1/workflows`: Full DAG CRUD, cycle/node validation, executions per workflow, and aggregate statistical metrics.
  - `/api/v1/executions`: Execution history with pagination, status/duration/incident filters, chronological spans, and DAG trace trees.
  - `/api/v1/simulator`: Causal chaos catalog (`/scenarios`), synchronous in-memory trace generation (`/generate`), and targeted chaos injection (`/inject-chaos`).
  - `/api/v1/services`: Microservice registry, profile update, latency percentiles, health summaries, and system topology graph (`/topology`).
  - RFC 7807 problem details exception handling (`apps/api/exceptions.py`) and typed Pydantic v2 schemas (`apps/api/schemas/`).
  - Comprehensive contract test suite with 48/48 passing tests and sub-millisecond to sub-15ms endpoint latencies.
* **Status**: Completed

---

## Milestone 4: Interactive Frontend Dashboard
* **Objective**: Build developer-grade React dashboard for telemetry, graph topology, trace waterfall timelines, and live simulation controls.
* **Deliverables**:
  - System Overview & Operations KPI dashboard (`OverviewView.tsx`) consuming single-pass telemetry summaries and incident feeds.
  - Interactive Service Dependency Topology graph visualizer (`TopologyView.tsx`) using `@xyflow/react` with clickable Service Inspector and live tuning editor.
  - Workflow DAG Explorer (`WorkflowsView.tsx`) visualizing topological step graphs, execution duration distributions (P50/P95), and execution feeds.
  - Execution Explorer & Distributed Trace Waterfall viewer (`ExecutionsView.tsx`) featuring Gantt timelines, span indentation, and SpanDetailDrawer.
  - Microservice Observability console (`ServicesView.tsx`) with database-side latency percentiles (P50..P99), error rates, and live capacity tuning.
  - TraceSim Chaos Workbench & Simulation Console (`SimulatorView.tsx`) with 7 scenario presets, synthetic trace generator, and targeted chaos injection.
  - Typed API client layer (`frontend/src/api/`) with RFC 7807 problem details error handling and dark-mode design system.
* **Status**: Completed

---

## Milestone 5: Event Streaming with Kafka
* **Objective**: Decouple trace generation and ingestion with asynchronous Kafka event streaming in KRaft mode.
* **Deliverables**:
  - `aiokafka`-based async event producer (`KafkaTraceEventProducer`) and consumer (`KafkaTraceEventConsumer`) in `packages/events/`.
  - Canonical `TraceEvent` JSON serialization with microsecond timestamp precision (`JsonTraceEventSerializer`).
  - Dual-mode event bus (`InMemoryEventBus`) providing 100% hermetic unit/integration testing without requiring a live Kafka broker.
  - Causal span partitioning by `execution_id` ensuring FIFO order for parent-child trace graphs.
  - Background streaming ingestion worker daemon (`apps/worker/stream_ingestor.py`) with micro-batching ($1,000$ events / $50\text{ms}$) and idempotent TimescaleDB persistence.
  - Real-time streaming discrete-event simulator emitter (`apps/simulator/streaming.py`).
  - Simulator REST API (`POST /api/v1/simulator/generate`) and frontend console toggle for streaming generation (`stream_to_kafka: bool`).
  - Docker Compose configuration for Apache Kafka in KRaft mode (zero Zookeeper) and `worker` service.
  - End-to-end benchmark achieving $> 27,000\text{ events/sec}$ consumer persistence throughput ($5.5\times$ target).
* **Status**: Completed

---

## Milestone 6: ML Failure & Latency Prediction Engine with TreeSHAP Explainability
* **Objective**: In-flight temporal feature extraction, calibrated gradient-boosted failure classification, execution duration regression, and TreeSHAP explainability.
* **Deliverables**:
  - In-flight temporal feature extraction pipeline (`apps/ml/features.py`) with 16 tabular features and strict zero future leakage guarantees.
  - Calibrated XGBoost failure classifier (`WorkflowFailureClassifier`) and continuous latency regressor (`WorkflowLatencyRegressor`).
  - TreeSHAP feature attribution explainer (`apps/ml/explainability.py`) computing exact additive attributions $\sum \phi_i(x) + \phi_0 = f(x)$ and human-readable diagnostic messages.
  - Model registry with disk persistence, joblib serialization, and automatic bootstrap training (`apps/ml/registry.py`).
  - Synthetic balanced dataset generator and training evaluation pipeline (`apps/ml/trainer.py`).
  - SQLAlchemy `PredictionModel` ORM entity and async `PredictionRepository`.
  - FastAPI prediction REST endpoints (`POST /api/v1/predictions/predict`, `GET /api/v1/predictions/executions/{id}`, `POST /api/v1/predictions/train`, `GET /api/v1/predictions/models`).
  - Interactive Frontend TreeSHAP visualizer drawer (`ShapAttributionDrawer.tsx`) and ML risk level badges on executions dashboard.
  - Comprehensive unit/integration test suite (68/68 passing tests) and ML inference benchmark (37,414 extractions/sec, P99 latency 4.37ms).
* **Status**: Completed

---

## Milestone 7: Unsupervised Anomaly Detection Engine
* **Objective**: Multi-detector unsupervised and statistical outlier engine detecting metric outliers, microservice latency spikes, illegal Markov DAG transition paths, retry storms, and cascading multi-service outages.
* **Deliverables**:
  - `WorkflowIsolationForestDetector`: Multidimensional prefix feature outlier detector with sigmoid calibration.
  - `ServiceLatencyAnomalyDetector`: Dynamic statistical IQR and MAD Z-score baselines per microservice.
  - `TransitionPathAnomalyDetector`: Markov DAG transition probability and cycle detection model.
  - `ErrorCascadeAnomalyDetector`: Retry storm bursts ($\ge 3$ retries) and cascading fault propagation engine.
  - `CompositeAnomalyDetector`: Ensemble priority aggregator scoring anomalies on normalized $[0.0, 1.0]$ severity scale.
  - `AnomalyDetectorRegistry`: Thread-safe singleton registry with versioned disk persistence and auto-bootstrap.
  - `AnomalyRepository` & `workflow_anomalies` schema: Async persistence for detected anomalies and diagnostic stats.
  - FastAPI REST API under `/api/v1/anomalies`: Detection, filtering, stats, and calibration endpoints.
  - Interactive React Anomaly Explorer dashboard (`AnomaliesView.tsx`) with metric cards, filters, and slide-out diagnostic evidence drawer.
* **Acceptance**:
  - Chaos Detection Recall: **100.0% (210/210 detected across 7 chaos presets, target $\ge 90\%$)** — PASSED.
  - Nominal False Positive Rate: **3.0% FPR (target $< 5\%$)** — PASSED.
  - Inference Latency: **P99 = 4.50ms (target $< 10\text{ms}$)**, **P50 = 2.22ms** — PASSED.
  - Test Suite: **74/74 passing** — PASSED.
* **Status**: Completed

---

## Milestone 8: Root Cause Engine & Graph-Based Deterministic Reasoning
* **Objective**: Graph-based deterministic reasoning identifying culprit dependencies, causal propagation chains, and multi-hypothesis ranking.
* **Deliverables**:
  - Temporal Causal DAG builder and upstream backward traversal algorithm.
  - Deterministic incident pattern matcher covering 7 canonical fault signatures.
  - Multi-criteria scoring integrating failure severity, retries, latency baselines, and TreeSHAP attributions.
  - Async database persistence (`workflow_root_causes`) and FastAPI routes (`/api/v1/root-cause`).
  - Interactive React RCA Explorer with visual propagation chain DAG.
  - Ground-truth benchmark achieving 100.0% attribution accuracy and P99 latency of 1.15ms (<10ms target).
* **Status**: Completed

---

## Milestone 9: Workflow Optimizer & Execution Path Routing
* **Objective**: Multi-objective path optimization, 3D Pareto frontier evaluation, transparent resource cost modeling, and advisory incident detour recommendations.
* **Deliverables**:
  - Transparent resource cost model distinguishing observed telemetry from modeled compute, DB I/O, and retry penalty units.
  - Multi-objective 3D Pareto optimal frontier calculator across Latency, Cost, and Reliability.
  - Historical trace path extractor with sample count tracking and statistical confidence calibration.
  - WorkflowOptimizer engine with weighted utility scoring, SLA constraint filters, and advisory incident diversion recommendations around M8 culprit components.
  - Async persistence (`workflow_optimizations` table & `OptimizationRepository`) and FastAPI endpoints (`/api/v1/optimizer`).
  - Interactive React Optimizer UI with 3D Pareto scatter visualizer, side-by-side workflow diff cards, and live auto-normalized weight sliders.
  - 1,000-run performance benchmark achieving P99 latency of 0.369ms (<10ms target), 6,045+ opt/sec throughput, and verifiable 15%–87.8% path improvements.
* **Status**: Completed

---

## Milestone 10: Tool-Grounded Conversational AI Analyst
* **Objective**: Conversational diagnostic assistant grounded by safe TraceMind tools, real-time citation verification, deterministic ReAct orchestration, and zero-hallucination guardrails.
* **Deliverables**:
  - Provider-agnostic LLM interface (`BaseLLMClient`, `MockLLMClient`, `OpenAILLMClient`).
  - Read-only Tool Registry bridging M0–M9 subsystems (`get_system_topology`, `get_trace_tree`, `get_risk_prediction_and_shap`, `get_anomalies`, `get_root_cause_diagnosis`, `get_workflow_optimization`).
  - Hard safety limits ($5$ tool calls max per turn, $2.0\text{s}$ timeout per tool call, strict read-only enforcement, payload truncation to prevent context explosion).
  - Fact-checking & Citation-Level Grounding Engine computing mathematical grounding scores and injecting numbered evidence citations.
  - Dual API transport contracts: Synchronous REST (`POST /api/v1/analyst/chat`) and Server-Sent Events streaming (`POST /api/v1/analyst/chat/stream`).
  - PostgreSQL persistence with cascade deletes (`analyst_conversations`, `analyst_messages`) and Alembic migration `002_analyst_tables.py`.
  - Interactive React AI Analyst dashboard (`AnalystView.tsx`) with conversation sessions, collapsible tool cards, interactive citation badges, and prompt starter chips.
  - 100-query benchmark achieving P99 latency of $1.505\text{ms}$ ($<25.0\text{ms}$ target), $1,894.5\text{ queries/sec}$ throughput, $95.75\%$ grounding score ($\ge 95.0\%$ target), and $0.0\%$ service hallucination rate.
* **Status**: Completed

---

## Milestone 11: Application Observability
* **Objective**: Instrument TraceMind backend, ML intelligence pipelines, and streaming workers with OpenTelemetry, Prometheus metrics exposition, correlation IDs, and pre-configured Grafana monitoring dashboards.
* **Deliverables**:
  - OpenTelemetry distributed tracing setup (`packages/observability/tracer.py`) supporting W3C `traceparent` headers (`00-{trace_id}-{span_id}-{flags}`) and context propagation.
  - Low-cardinality Prometheus metrics catalog (`packages/observability/metrics.py`) and FastAPI exposition endpoint `GET /metrics` (`tracemind_http_requests_total`, `tracemind_http_request_duration_seconds`, `tracemind_ml_inference_duration_seconds`, `tracemind_anomalies_detected_total`, `tracemind_root_cause_diagnoses_total`, `tracemind_workflow_optimizations_total`, `tracemind_analyst_grounding_score`, `tracemind_kafka_messages_ingested_total`).
  - FastAPI `TracingAndMetricsMiddleware` binding `trace_id` and `span_id` to structlog context and attaching `X-Trace-Id` and `X-Span-Id` response headers.
  - Structlog OpenTelemetry context processor (`add_opentelemetry_context`) ensuring 100% of backend and worker logs contain correlation identifiers.
  - Subsystem telemetry instrumentation across ML prediction endpoints, Anomaly detectors, Root cause diagnoses, 3D Pareto optimizer, AI Analyst turns, and Kafka streaming ingestor.
  - Fail-open resilience: zero unhandled telemetry exceptions can disrupt API operations.
  - Docker Compose monitoring stack (`docker-compose.yml`) provisioning Prometheus (`prom/prometheus:v2.53.0`) on port `9090` and Grafana (`grafana/grafana:11.1.0`) on port `3000`.
  - Automated Grafana provisioning (`datasource.yml`, `dashboard_provider.yml`, `tracemind_observability_dashboard.json`) featuring 8 interactive visualization panels.
  - 1,000-iteration latency overhead benchmark verifying $\Delta\text{P99} = +0.245\text{ms}$ ($<0.500\text{ms}$ target) and $\Delta\text{Mean} = +0.088\text{ms}$ ($<0.200\text{ms}$ target).
* **Status**: Completed

---

## Milestone 12: Production Containerization & Cloud Deployment
* **Objective**: Deliver enterprise-ready, hardened multi-stage container images, production Docker Compose topologies, cloud-ready Kubernetes manifests, pre-deployment database migration lifecycles, and automated production smoke tests.
* **Deliverables**:
  - Hardened multi-stage Dockerfiles (`infrastructure/docker/`) for API Gateway (`Dockerfile.api`), Streaming Worker (`Dockerfile.worker`), Schema Migrator (`Dockerfile.migrator`), and Frontend UI (`Dockerfile.frontend`).
  - Container security hardening: non-root execution (`tracemind:10001`), dropped capabilities (`cap_drop: [ALL]`), `no-new-privileges: true`, and slim runtime layers.
  - Production Nginx reverse-proxy configuration (`infrastructure/docker/nginx.conf`) with enterprise security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options), static asset caching, and SPA fallback routing.
  - Production Docker Compose stack (`docker-compose.prod.yml`) with CPU/Memory limits, logging rotation, healthchecks, isolated bridge network, and persistent named volumes.
  - Cloud-ready declarative Kubernetes manifests (`infrastructure/k8s/`) covering Namespace, ConfigMap, Secrets template, Migration Job, API Deployment with HPA (2–10 replicas), Worker Deployment, Frontend Deployment, Services, and Ingress with TLS.
  - Automated CI/CD deployment workflow (`.github/workflows/deploy.yml`) with Docker layer caching, Trivy security vulnerability scanning, and dry-run validation.
  - Zero-dependency production smoke test suite ([`scripts/smoke_test.py`](file:///c:/Users/Rishabh.Gupta/Personal_Projects/TraceMind/scripts/smoke_test.py)) validating all 11 subsystems end-to-end with 100% pass rate.
* **Status**: Completed

---

## Milestone 13: Large-Scale HPC Performance Experiments (1M+ Traces)
* **Objective**: Scale TraceMind to 1M+ traces with multiprocessing, streaming chunk pipelines, vectorized matrix inference, and publish a comprehensive HPC scalability research whitepaper.
* **Deliverables**:
  - Cross-platform hardware discovery and statistical performance profiler (`packages/common/profiler.py`) with percentile distribution tracking ($P_{50}, P_{90}, P_{95}, P_{99}$) and process memory tracking (RSS/WSS).
  - High-performance parallel discrete-event trace simulator (`apps/simulator/parallel_engine.py`) supporting deterministic chunked multiprocessing and bounded memory generators (`stream_chunks`).
  - Comprehensive 7-suite HPC benchmark harness (`benchmarks/benchmark_hpc_scalability.py`) benchmarking parallel simulation, streaming ingestion, TimescaleDB bulk writes, batched XGBoost matrix inference, TreeSHAP attributions, unsupervised anomaly scoring, causal graph RCA, 3D Pareto optimization, and 50-turn concurrent grounded AI Analyst queries.
  - Multi-scale tier experiment execution across 10K, 100K, and 1,000,000+ traces (18.9M events).
  - Peak RSS memory verification strictly maintaining $\le 748.2\text{ MB}$ ($< 2.0\text{ GB}$ budget).
  - Published research benchmark whitepaper (`docs/research/hpc_scalability_report.md`).
* **Status**: Completed

---

## Milestone 14: Autonomous Closed-Loop Remediation & Policy-Governed Actuation
* **Objective**: Transform TraceMind from an observational and analytical system into a self-healing operational runtime control plane with deterministic safety invariants, exact-state rollback, multi-protocol actuators, and cryptographic audit ledgers.
* **Deliverables**:
  - Domain models (`packages/domain/remediation.py`) for `ActionType`, `ExecutionMode` (`AUTONOMOUS`, `SUPERVISED`, `ADVISORY`), `ActionPlanStatus`, `StateSnapshot`, `RemediationPolicy`, `SafetyCheckReport`, and `RemediationActionPlan`.
  - Deterministic Safety Invariant Evaluator (`apps/ml/remediation/safety_guards.py`) enforcing blast-radius limits ($\le 30\%$), anti-flapping/cooldown ($300\text{s}$ cooldown, $\le 3$ actuations/hr), causal dependency acyclicity (rejecting routes with active culprits), and target path capacity headroom ($\ge 40\%$).
  - Policy Engine (`apps/ml/remediation/policy_engine.py`) pre-seeded with 7 canonical self-healing policies and strict mode escalation resolution.
  - Action Planner (`apps/ml/remediation/planner.py`) synthesizing remediation plans from RCA and Pareto optimizations with deterministic SHA-256 idempotency keys.
  - Concurrency-safe, atomic multi-protocol actuator plane (`InMemoryRoutingActuator`, dry-run `HttpGatewayActuator`, HMAC-SHA256 `WebhookActuator`).
  - Cryptographic append-only Audit Ledger (`apps/ml/remediation/audit_ledger.py`) generating tamper-evident SHA-256 hash chains.
  - Post-Actuation Health Verifier (`apps/ml/remediation/verifier.py`) with automated verbatim exact-state rollback upon degraded telemetry.
  - Database persistence layer (`remediation_policies`, `remediation_action_plans`, `remediation_audit_ledger` tables & `RemediationRepository`).
  - 11 RESTful endpoints (`/api/v1/remediations/*`) and 4 AI Analyst self-healing tool handlers (`simulate_remediation`, `actuate_mitigation`, `rollback_mitigation`, `get_remediation_mesh_state`).
  - Interactive React Frontend Control Center (`RemediationView.tsx`, `PolicyEditorModal.tsx`, `PlanDetailsModal.tsx`, `RemediationActionCard.tsx`).
  - Quantitative 6-suite benchmark (`benchmarks/benchmark_remediation.py`) validating $18,981\text{ plans/sec}$ synthesis throughput, $54,612\text{ actuations/sec}$ actuation, $53,792\text{ rollbacks/sec}$ rollback, $100\%$ safety invariant rejection rate, $100\%$ audit chain integrity, and $100\%$ closed-loop recovery rate across 7 chaos presets.
* **Status**: Completed

---

## Milestone 15: Enterprise Multi-Tenancy, Zero-Trust RS256 Security & Governance
* **Objective**: Transform TraceMind into a enterprise multi-tenant platform featuring Zero-Trust RS256 asymmetric cryptographic authentication, strict tenant data isolation, granular 5-tier RBAC enforcement, Argon2id password hashing, AES-256-GCM envelope encryption, anti-spoofing defense, in-memory sliding-window rate limiting, and an interactive security management UI.
* **Deliverables**:
  - Multi-tenant data scoping with `tenant_id` columns and compound indexes across all 10 domain entities and database tables.
  - Zero-Trust RS256 asymmetric JWT engine (`JWTTokenManager`) supporting 15-minute access tokens, 7-day single-use refresh token rotation, and atomic revocation blocklisting.
  - Granular RBAC matrix with 5 roles (`PLATFORM_ADMIN`, `TENANT_ADMIN`, `OPERATOR`, `ANALYST`, `VIEWER`) and 24 fine-grained permissions protecting all REST/streaming endpoints.
  - Anti-spoofing defense rejecting `X-Tenant-Id` header mismatches unless requested by authenticated `PLATFORM_ADMIN`.
  - Non-bypassable M14 remediation safety invariant shield ensuring even administrative users cannot actuate unsafe remediation plans.
  - Cryptographic envelope cipher (`AES256GCMCipher`) with authenticated `v1:<key_id>:<nonce>:<ciphertext>:<tag>` envelopes and Argon2id password hashing.
  - High-throughput in-memory sliding-window rate limiter per tenant/IP (797k+ checks/sec).
  - Security REST API (`/api/v1/auth/*`, `/api/v1/tenants/*`, `/api/v1/api-keys/*`).
  - Interactive React Frontend Security Center (`SecurityView.tsx`, `AuthContext.tsx`, `auth.ts`) for token sessions, tenant switching, API key lifecycle management, and user provisioning.
  - Quantitative security microbenchmark suite (`benchmarks/benchmark_security.py`) confirming AES-256-GCM at 290k ops/s, RS256 verification at 36.5k ops/s (27.2 µs mean latency), and rate limiting at 797k ops/s.
* **Status**: Completed



