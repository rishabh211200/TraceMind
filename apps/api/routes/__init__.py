"""FastAPI route modules package export."""

from apps.api.routes.incidents import router as incidents_router
from apps.api.routes.services import router as services_router
from apps.api.routes.traces import router as traces_router

__all__ = ["traces_router", "services_router", "incidents_router"]
