# ADR-001: TraceMind Project Foundation & Core Technology Stack

## Status
Accepted

## Date
2026-08-15

## Context
TraceMind is an AI-powered platform designed to learn behavioral patterns from distributed system execution traces. The project requires:
1. High-throughput synthetic trace generation.
2. Robust domain modeling and asynchronous API design.
3. Modular separation between simulation, persistence, machine learning, and AI services.
4. Rich, developer-oriented visualization frontend.
5. Strict reproducible experimentation and portfolio-grade engineering standards.

## Decisions

### 1. Monorepo Structure
We adopt a modular monorepo structure separating `apps/` (API, Simulator, ML, AI), `packages/` (Domain, Database, Events, Workflow, Common), `frontend/` (React/Vite/TS), `migrations/`, and `tests/`.
* **Rationale**: Simplifies co-versioning of domain models and schemas between backend services, simulator, and test suites without overhead of multiple repositories.

### 2. Python 3.12+ & FastAPI for Backend
We select Python 3.12+ paired with FastAPI and Pydantic v2.
* **Rationale**: Python provides native support for simulation (`SimPy`), data science (`Pandas`, `NumPy`), graph theory (`NetworkX`), and ML (`XGBoost`, `SHAP`). FastAPI enables high-performance async REST APIs with automatic OpenAPI schema generation.

### 3. Progressive Infrastructure Adoption
Infrastructure dependencies are phased across milestones:
* **Milestone 0-4**: Direct Async SQLAlchemy + PostgreSQL + Redis.
* **Milestone 5+**: Kafka event streaming introduced for high-throughput async processing.
* **Milestone 6+**: MLflow for model registry and experiment tracking.
* **Milestone 11+**: OpenTelemetry, Prometheus, and Grafana for observability.
* **Rationale**: Prevents premature microservice and distributed streaming complexity until basic domain, simulator, and persistence layers are robustly tested.

### 4. React 18, TypeScript & Tailwind CSS for Frontend
The frontend uses React with TypeScript, bundled by Vite, and styled with Tailwind CSS.
* **Rationale**: Fast HMR development cycles, strict typing matching backend domain models, and high-performance graph visualizations via React Flow.

### 5. Deterministic & Ground-Truth Oriented ML
All simulation scenarios record ground-truth causal factors alongside generated traces. ML models and root cause engines are evaluated directly against these ground-truth labels.
* **Rationale**: Guarantees scientific validity and verifiable metrics rather than subjective evaluation.

### 6. Tool-Grounded LLM Integration
The AI Analyst operates strictly via explicit, read-only tools without direct database access.
* **Rationale**: Prevents prompt injection vulnerabilities, database lockouts, and AI hallucinations by grounding all answers in deterministic facts and structured predictions.

## Consequences
* Fast local development with minimal initial infrastructure overhead.
* Clear migration path towards streaming and distributed scaling in later milestones.
* All code remains typed, tested, and linted under strict CI pipelines.
