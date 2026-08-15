# TraceMind API Documentation

This directory contains API specifications, schemas, and contract documentation for TraceMind.

* **Interactive OpenAPI Specs**: Available at runtime via `/docs` (Swagger UI) and `/redoc` (ReDoc).
* **Versioning**: All operational endpoints are versioned under `/api/v1/`.

## Core Endpoint Groups

* `/api/v1/health`: System health and module operational states.
* `/api/v1/workflows`: Workflow graph definitions and topology metrics.
* `/api/v1/executions`: Execution run querying, span waterflow retrieval, and status tracking.
* `/api/v1/services`: Distributed service definitions and baseline metrics.
* `/api/v1/predictions`: ML failure risk predictions and SHAP explanations.
* `/api/v1/anomalies`: Flagged workflow and latency anomalies.
* `/api/v1/root-cause`: Causal graph hypotheses for executions.
* `/api/v1/recommendations`: Optimization and routing strategies.
* `/api/v1/simulator`: Synthetic trace generation and incident injection.
* `/api/v1/ai/analyze`: Tool-calling AI analyst queries.
