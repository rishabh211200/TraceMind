"""FastAPI route modules package export."""

from apps.api.routes.anomalies import router as anomalies_router
from apps.api.routes.executions import router as executions_router
from apps.api.routes.incidents import router as incidents_router
from apps.api.routes.predictions import router as predictions_router
from apps.api.routes.services import router as services_router
from apps.api.routes.simulator import router as simulator_router
from apps.api.routes.traces import router as traces_router
from apps.api.routes.workflows import router as workflows_router

__all__ = [
    "workflows_router",
    "executions_router",
    "traces_router",
    "simulator_router",
    "services_router",
    "incidents_router",
    "predictions_router",
    "anomalies_router",
]
