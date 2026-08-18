"""TraceMind Canonical Event Serializers.

Provides robust JSON and byte serialization for distributed TraceEvent records,
guaranteeing microsecond datetime precision and full Pydantic v2 validation.
"""

from typing import Protocol, TypeVar

from packages.domain.events import TraceEvent

T = TypeVar("T")


class EventSerializer(Protocol[T]):
    """Generic serialization protocol for streaming event schemas."""

    def serialize(self, event: T) -> bytes:
        """Serialize an event object into binary payload."""
        ...

    def deserialize(self, payload: bytes) -> T:
        """Deserialize binary payload into a validated event object."""
        ...


class JsonTraceEventSerializer:
    """Canonical JSON serializer/deserializer for TraceEvent domain instances."""

    def serialize(self, event: TraceEvent) -> bytes:
        """Serialize a TraceEvent into UTF-8 JSON bytes."""
        if not isinstance(event, TraceEvent):
            raise TypeError(f"Expected TraceEvent instance, got {type(event).__name__}")
        return event.model_dump_json().encode("utf-8")

    def deserialize(self, payload: bytes) -> TraceEvent:
        """Deserialize UTF-8 JSON bytes into a fully validated TraceEvent instance."""
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"Expected bytes or bytearray payload, got {type(payload).__name__}")
        return TraceEvent.model_validate_json(payload)


# Module-level convenience functions
_default_serializer = JsonTraceEventSerializer()


def serialize_trace_event(event: TraceEvent) -> bytes:
    """Serialize a TraceEvent using the default canonical JSON serializer."""
    return _default_serializer.serialize(event)


def deserialize_trace_event(payload: bytes) -> TraceEvent:
    """Deserialize raw bytes into a TraceEvent using the default canonical JSON serializer."""
    return _default_serializer.deserialize(payload)
