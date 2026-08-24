"""Unit tests for Causal Graph builder and upstream backward traversal."""

from datetime import UTC, datetime, timedelta

from apps.ml.root_cause.causal_graph import CausalGraphBuilder, CausalGraphTraverser
from packages.domain.events import EventStatus, EventType, TraceEvent


def test_causal_graph_builder_and_traversal():
    builder = CausalGraphBuilder()
    traverser = CausalGraphTraverser()

    now = datetime.now(UTC)
    events = [
        TraceEvent(
            event_id="e1",
            execution_id="exec_1",
            workflow_id="order_fulfillment",
            service="api-gateway",
            operation="route",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=10.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="e2",
            execution_id="exec_1",
            workflow_id="order_fulfillment",
            service="order-service",
            operation="process",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=25.0,
            timestamp=now + timedelta(milliseconds=10),
        ),
        TraceEvent(
            event_id="e3",
            execution_id="exec_1",
            workflow_id="order_fulfillment",
            service="inventory-db",
            operation="query",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.FAILURE,
            latency_ms=1200.0,
            timestamp=now + timedelta(milliseconds=35),
        ),
    ]

    anomalies = [
        {
            "id": "a1",
            "anomaly_type": "LATENCY_SPIKE",
            "score": 0.85,
            "affected_services": ["inventory-db"],
        }
    ]

    shap_contribs = [{"feature_name": "inventory_service_duration_ms", "contribution": 0.42}]

    graph = builder.build_graph(events, anomalies=anomalies, shap_contributions=shap_contribs)

    assert len(graph.nodes) == 3
    assert "inventory-db" in graph.service_nodes
    assert graph.nodes["e3"].is_failure is True
    assert len(graph.nodes["e3"].anomalies) == 1

    # Traverse backwards from failure symptom
    symptoms = traverser.find_symptom_nodes(graph)
    assert len(symptoms) >= 1
    assert symptoms[0].service == "inventory-db"

    paths = traverser.backward_traverse(graph, symptoms)
    assert len(paths) >= 1
    assert paths[0][0] == "api-gateway"
    assert paths[0][-1] == "inventory-db"
