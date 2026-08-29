"""OpenTelemetry distributed tracing setup, W3C traceparent propagation, and context managers."""

import re
import uuid
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Span, Tracer

from packages.common.logging import get_logger

logger = get_logger("tracemind.observability.tracer")

F = TypeVar("F", bound=Callable[..., Any])

_tracer_initialized = False
_tracer_provider: TracerProvider | None = None
_default_tracer: Tracer | None = None

W3C_TRACEPARENT_REGEX = re.compile(r"^00-([0-9a-fA-F]{32})-([0-9a-fA-F]{16})-([0-9a-fA-F]{2})$")


def generate_trace_id() -> str:
    """Generate a valid 128-bit (32 hex character) trace ID."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a valid 64-bit (16 hex character) span ID."""
    return uuid.uuid4().hex[:16]


def format_w3c_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Format standard W3C traceparent header value (00-trace_id-span_id-flags)."""
    clean_trace = trace_id.replace("-", "").lower()[:32].zfill(32)
    clean_span = span_id.replace("-", "").lower()[:16].zfill(16)
    flags = "01" if sampled else "00"
    return f"00-{clean_trace}-{clean_span}-{flags}"


def parse_w3c_traceparent(traceparent: str | None) -> tuple[str | None, str | None, bool]:
    """Parse W3C traceparent header into (trace_id, parent_span_id, sampled)."""
    if not traceparent:
        return None, None, False

    match = W3C_TRACEPARENT_REGEX.match(traceparent.strip())
    if not match:
        return None, None, False

    trace_id = match.group(1).lower()
    parent_span_id = match.group(2).lower()
    flags = match.group(3)
    sampled = (int(flags, 16) & 0x01) == 1

    # Invalidate all-zeros IDs per W3C specification
    if trace_id == "0" * 32 or parent_span_id == "0" * 16:
        return None, None, False

    return trace_id, parent_span_id, sampled


def init_tracer(
    service_name: str = "tracemind-api", enable_console_exporter: bool = False
) -> Tracer:
    """Initialize OpenTelemetry TracerProvider and register with global trace manager."""
    global _tracer_initialized, _tracer_provider, _default_tracer

    if _tracer_initialized and _default_tracer:
        return _default_tracer

    try:
        resource = Resource.create(
            attributes={"service.name": service_name, "service.version": "0.11.0"}
        )
        provider = TracerProvider(resource=resource)

        if enable_console_exporter:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _tracer_provider = provider
        _default_tracer = trace.get_tracer(service_name)
        _tracer_initialized = True
        logger.info("opentelemetry_tracer_initialized", service_name=service_name)
        return _default_tracer
    except Exception as exc:
        logger.warning("opentelemetry_init_failed_fallback_to_noop", error=str(exc))
        return trace.get_tracer(service_name)


def get_tracer(service_name: str = "tracemind-api") -> Tracer:
    """Get active OpenTelemetry tracer or initialize a new one."""
    if not _tracer_initialized:
        return init_tracer(service_name)
    return trace.get_tracer(service_name)


@contextmanager
def trace_span(
    name: str, attributes: dict[str, Any] | None = None
) -> Generator[Span | None, None, None]:
    """Synchronous context manager for creating and recording an OpenTelemetry span with fail-open guarantee."""
    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(
                        k, str(v) if not isinstance(v, (int, float, bool, str)) else v
                    )
            yield span
    except Exception as exc:
        logger.warning("trace_span_execution_failed", span_name=name, error=str(exc))
        yield None


@asynccontextmanager
async def trace_async_span(
    name: str, attributes: dict[str, Any] | None = None
) -> AsyncGenerator[Span | None, None]:
    """Asynchronous context manager for creating and recording an OpenTelemetry span."""
    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(
                        k, str(v) if not isinstance(v, (int, float, bool, str)) else v
                    )
            yield span
    except Exception as exc:
        logger.warning("trace_async_span_failed", span_name=name, error=str(exc))
        yield None
