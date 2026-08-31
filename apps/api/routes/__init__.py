"""FastAPI route modules package export."""

from apps.api.routes.analyst import router as analyst_router
from apps.api.routes.anomalies import router as anomalies_router
from apps.api.routes.api_keys import router as api_keys_router
from apps.api.routes.auth import router as auth_router
from apps.api.routes.executions import router as executions_router
from apps.api.routes.incidents import router as incidents_router
from apps.api.routes.optimizer import router as optimizer_router
from apps.api.routes.predictions import router as predictions_router
from apps.api.routes.remediation import router as remediation_router
from apps.api.routes.root_cause import router as root_cause_router
from apps.api.routes.services import router as services_router
from apps.api.routes.simulator import router as simulator_router
from apps.api.routes.tenants import router as tenants_router
from apps.api.routes.traces import router as traces_router
from apps.api.routes.workflows import router as workflows_router

__all__ = [
    "auth_router",
    "tenants_router",
    "api_keys_router",
    "workflows_router",
    "executions_router",
    "traces_router",
    "simulator_router",
    "services_router",
    "incidents_router",
    "predictions_router",
    "anomalies_router",
    "root_cause_router",
    "optimizer_router",
    "analyst_router",
    "remediation_router",
]
