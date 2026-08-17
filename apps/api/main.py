"""TraceMind FastAPI Application entrypoint and core routing."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from apps.api.routes import incidents_router, services_router, traces_router
from packages.common.config import get_settings
from packages.common.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(log_level=settings.log_level)
logger = get_logger("tracemind.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown event lifecycle."""
    logger.info(
        "starting_tracemind_api",
        environment=settings.environment,
        debug=settings.debug,
    )
    yield
    logger.info("stopping_tracemind_api")


app = FastAPI(
    title="TraceMind API",
    description="AI-Powered Distributed Workflow Intelligence Platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# Mount API Routers
app.include_router(traces_router)
app.include_router(services_router)
app.include_router(incidents_router)


class HealthResponse(BaseModel):
    """Health check status response schema."""

    status: str
    version: str
    environment: str
    modules: dict[str, str]


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
        version="0.1.0",
        environment=settings.environment,
        modules={
            "api": "operational",
            "simulator": "ready",
            "trace_store": "ready",
            "intelligence": "ready",
            "ml_engine": "ready",
            "root_cause_engine": "ready",
            "workflow_optimizer": "ready",
            "ai_analyst": "ready",
        },
    )


@app.get(
    "/",
    tags=["System"],
    summary="Root API info",
)
async def root() -> dict[str, Any]:
    """Root endpoint redirecting developers to OpenAPI documentation."""
    return {
        "service": "TraceMind Workflow Intelligence Platform",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
