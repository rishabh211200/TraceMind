"""TraceMind FastAPI Application entrypoint and core routing."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from apps.api.exceptions import register_exception_handlers
from apps.api.routes import (
    anomalies_router,
    executions_router,
    incidents_router,
    optimizer_router,
    predictions_router,
    root_cause_router,
    services_router,
    simulator_router,
    traces_router,
    workflows_router,
)
from packages.common.config import get_settings
from packages.common.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(log_level=settings.log_level)
logger = get_logger("tracemind.api")

OPENAPI_TAGS = [
    {
        "name": "Workflows",
        "description": "Workflow DAG definition registration, DAG cycle validation, execution listings, and aggregate metrics.",
    },
    {
        "name": "Executions & Traces",
        "description": "Workflow execution history, chronological span event streams, and recursive DAG tree reconstructions.",
    },
    {
        "name": "Intelligence & ML Engine",
        "description": "In-flight workflow failure & latency predictions, TreeSHAP feature attributions, and ML model lifecycle management.",
    },
    {
        "name": "Anomalies & Outlier Detection",
        "description": "Unsupervised and statistical anomaly detection: Isolation Forest, service latency spikes, unusual DAG paths, and error cascades.",
    },
    {
        "name": "Root Cause Engine",
        "description": "Deterministic causal graph reasoning, upstream back-traversal, incident pattern matching, and multi-hypothesis ranking.",
    },
    {
        "name": "Optimizer",
        "description": "Multi-objective Pareto optimal routing, historical path evaluation, and advisory incident diversion recommendations.",
    },
    {
        "name": "Simulator & Chaos Controls",
        "description": "Deterministic synthetic trace simulation generation, chaos scenario catalog, and targeted chaos injection.",
    },
    {
        "name": "Services & Telemetry",
        "description": "Microservice profile registry, graph dependency topology, database-side latency percentiles, and operational health summaries.",
    },
    {
        "name": "Incidents & Ground Truth",
        "description": "Ground-truth chaos incident records, affected services, and incident-impacted workflow executions.",
    },
    {
        "name": "System",
        "description": "System health checks, environment diagnostics, and module readiness statuses.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for FastAPI startup and graceful shutdown."""
    logger.info(
        "starting_tracemind_api",
        version="0.9.0",
        environment=settings.environment,
        debug=settings.debug,
    )
    try:
        from packages.database.session import get_async_engine, init_db

        engine = get_async_engine()
        await init_db(engine)
    except Exception as exc:
        logger.warning("db_init_warning", error=str(exc))

    yield
    logger.info("stopping_tracemind_api")


app = FastAPI(
    title="TraceMind API",
    description="AI-Powered Distributed Workflow Intelligence Platform REST API",
    version="0.9.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

# Configure Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register standardized error handlers (RFC 7807)
register_exception_handlers(app)

# Mount API Routers
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(predictions_router)
app.include_router(anomalies_router)
app.include_router(root_cause_router)
app.include_router(optimizer_router)
app.include_router(traces_router)  # Preserved for Milestone 2 client compatibility
app.include_router(simulator_router)
app.include_router(services_router)
app.include_router(incidents_router)


class HealthResponse(BaseModel):
    """Health check status response schema."""

    status: str
    version: str
    environment: str
    modules: dict[str, str]


@app.get(
    "/",
    tags=["System"],
    summary="API Root Metadata",
)
async def root_metadata() -> dict[str, Any]:
    """Retrieve top-level API metadata and documentation links."""
    return {
        "service": "TraceMind Distributed Workflow Intelligence API",
        "version": "0.9.0",
        "environment": settings.environment,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/api/v1/health",
    }


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"],
    summary="System Health & Module Status",
)
async def health_check() -> HealthResponse:
    """Retrieve operational status for API and system modules."""
    return HealthResponse(
        status="healthy",
        version="0.9.0",
        environment=settings.environment,
        modules={
            "api": "operational",
            "simulator": "ready",
            "trace_store": "ready",
            "intelligence": "ready",
            "ml_engine": "ready",
            "anomaly_detector": "ready",
            "root_cause_engine": "operational",
            "optimizer": "operational",
        },
    )
