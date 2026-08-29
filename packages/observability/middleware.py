"""FastAPI middleware for OpenTelemetry request tracing, correlation ID binding, and Prometheus metrics."""

import re
import time
from collections.abc import Callable
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from packages.common.logging import get_logger
from packages.observability.metrics import record_http_request
from packages.observability.tracer import (
    format_w3c_traceparent,
    generate_span_id,
    generate_trace_id,
    parse_w3c_traceparent,
)

logger = get_logger("tracemind.observability.middleware")

# Regex pattern for normalizing dynamic IDs in route paths (low cardinality rule)
DYNAMIC_ID_PATTERN = re.compile(
    r"/(exec_[a-zA-Z0-9_-]+|rc_[a-zA-Z0-9_-]+|opt_[a-zA-Z0-9_-]+|conv_[a-zA-Z0-9_-]+|msg_[a-zA-Z0-9_-]+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\d+)"
)


def normalize_endpoint_path(path: str) -> str:
    """Normalize raw URL path by replacing dynamic resource IDs with generic placeholders."""
    if not path or path == "/":
        return "/"
    # Clean trailing slashes
    clean_path = path.rstrip("/") if len(path) > 1 else path
    # Replace dynamic entity IDs
    normalized = DYNAMIC_ID_PATTERN.sub("/:id", clean_path)
    return normalized


class TracingAndMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware combining OpenTelemetry W3C distributed trace context and Prometheus metrics."""

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        start_time = time.perf_counter()

        # 1. Parse or initialize W3C Trace Context (Fail-Open)
        raw_traceparent = request.headers.get("traceparent")
        raw_x_trace_id = request.headers.get("x-trace-id")

        trace_id, parent_span_id, sampled = parse_w3c_traceparent(raw_traceparent)
        if not trace_id:
            trace_id = raw_x_trace_id or generate_trace_id()

        span_id = generate_span_id()
        w3c_header = format_w3c_traceparent(trace_id, span_id, sampled=True)

        # 2. Bind Correlation IDs into structlog context
        try:
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
                trace_id=trace_id,
                span_id=span_id,
                http_method=request.method,
                http_path=request.url.path,
            )
        except Exception:
            pass  # Fail-open guarantee

        # 3. Process the HTTP request
        status_code = 500
        response: Response
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            logger.error("http_request_unhandled_exception", error=str(exc), path=request.url.path)
            raise
        finally:
            elapsed_seconds = time.perf_counter() - start_time
            norm_endpoint = normalize_endpoint_path(request.url.path)

            # 4. Record Prometheus Metrics (Fail-Open)
            try:
                record_http_request(
                    method=request.method,
                    endpoint=norm_endpoint,
                    status_code=status_code,
                    duration_seconds=elapsed_seconds,
                )
            except Exception as metric_err:
                logger.warning("metrics_recording_failed", error=str(metric_err))

        # 5. Inject W3C and correlation headers on outbound response
        try:
            response.headers["traceparent"] = w3c_header
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Span-Id"] = span_id
        except Exception:
            pass

        return response
