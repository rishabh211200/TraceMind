"""Structured logging setup for TraceMind services."""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.types import Processor


def add_opentelemetry_context(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Inject active OpenTelemetry trace and span IDs if not already present in context."""
    try:
        from opentelemetry import trace

        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            ctx = current_span.get_span_context()
            if ctx and ctx.is_valid:
                if "trace_id" not in event_dict:
                    event_dict["trace_id"] = format(ctx.trace_id, "032x")
                if "span_id" not in event_dict:
                    event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        pass  # Fail-open guarantee
    return event_dict


def configure_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    """Configure structlog and standard logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_opentelemetry_context,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    processors: list[Processor]
    if json_format or not sys.stderr.isatty():
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,
    )


def get_logger(name: str) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
