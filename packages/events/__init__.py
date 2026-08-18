"""TraceMind Events package: Streaming event bus abstractions and Kafka producers/consumers."""

from packages.events.bus import InMemoryEventBus, create_consumer, create_producer
from packages.events.consumer import (
    AsyncTraceEventConsumer,
    InMemoryTraceEventConsumer,
    KafkaTraceEventConsumer,
)
from packages.events.producer import (
    AsyncTraceEventProducer,
    InMemoryTraceEventProducer,
    KafkaTraceEventProducer,
)
from packages.events.serializers import (
    EventSerializer,
    JsonTraceEventSerializer,
    deserialize_trace_event,
    serialize_trace_event,
)

__version__ = "0.2.0"

__all__ = [
    "AsyncTraceEventConsumer",
    "AsyncTraceEventProducer",
    "EventSerializer",
    "InMemoryEventBus",
    "InMemoryTraceEventConsumer",
    "InMemoryTraceEventProducer",
    "JsonTraceEventSerializer",
    "KafkaTraceEventConsumer",
    "KafkaTraceEventProducer",
    "create_consumer",
    "create_producer",
    "deserialize_trace_event",
    "serialize_trace_event",
]
