"""Standardized API exceptions and error response handlers (RFC 7807)."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standardized API error response schema conforming to RFC 7807."""

    type: str = Field(
        default="about:blank",
        description="URI reference identifying the problem type",
    )
    title: str = Field(description="Short human-readable summary of problem")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Human-readable explanation specific to this occurrence")
    instance: str | None = Field(
        default=None, description="URI reference identifying specific occurrence"
    )
    error_code: str = Field(description="Application-specific error code")
    invalid_params: list[dict[str, Any]] | None = Field(
        default=None, description="List of invalid fields for validation errors"
    )


class APIException(Exception):
    """Base API exception class."""

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        title: str = "Internal Server Error",
        detail: str = "An unexpected error occurred.",
        error_code: str = "INTERNAL_ERROR",
        invalid_params: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.error_code = error_code
        self.invalid_params = invalid_params


class EntityNotFoundException(APIException):
    """404 Not Found exception."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Entity Not Found",
            detail=f"{entity_type} with ID '{entity_id}' was not found.",
            error_code=f"{entity_type.upper()}_NOT_FOUND",
        )


class ValidationException(APIException):
    """400 Bad Request or DAG validation exception."""

    def __init__(
        self,
        detail: str,
        title: str = "Validation Error",
        error_code: str = "VALIDATION_ERROR",
        invalid_params: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            title=title,
            detail=detail,
            error_code=error_code,
            invalid_params=invalid_params,
        )


class ConflictException(APIException):
    """409 Conflict exception."""

    def __init__(self, detail: str, error_code: str = "CONFLICT") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            title="Resource Conflict",
            detail=detail,
            error_code=error_code,
        )


class SimulationException(APIException):
    """Simulation engine execution failure."""

    def __init__(self, detail: str, error_code: str = "SIMULATION_ERROR") -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Simulation Execution Error",
            detail=detail,
            error_code=error_code,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with FastAPI application."""

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
        error_payload = ErrorDetail(
            title=exc.title,
            status=exc.status_code,
            detail=exc.detail,
            instance=str(request.url.path),
            error_code=exc.error_code,
            invalid_params=exc.invalid_params,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload.model_dump(exclude_none=True),
        )
