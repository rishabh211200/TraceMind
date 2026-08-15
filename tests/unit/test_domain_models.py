"""Unit tests for domain model instantiation and schema integrity."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.domain.incident import Incident, IncidentScenario, Severity
from packages.domain.intelligence import (
    Anomaly,
    AnomalyType,
    FeatureContribution,
    Prediction,
    Recommendation,
    RootCauseHypothesis,
)
from packages.domain.service import ServiceDefinition
from packages.domain.workflow import (
    ExecutionStatus,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowNode,
    WorkflowNodeType,
)


def test_trace_event_creation():
    """Verify TraceEvent serialization and defaults."""
    event = TraceEvent(
        execution_id="exec_123",
        workflow_id="order_flow",
        service="payment-service",
        operation="authorize_payment",
        event_type=EventType.SERVICE_COMPLETED,
        status=EventStatus.SUCCESS,
        latency_ms=125.4,
    )
    assert event.event_id.startswith("evt_")
    assert event.latency_ms == 125.4
    assert event.status == EventStatus.SUCCESS
    assert isinstance(event.timestamp, datetime)


def test_trace_event_negative_latency_rejected():
    """Verify validation constraint on negative latency."""
    with pytest.raises(ValidationError):
        TraceEvent(
            execution_id="exec_123",
            workflow_id="order_flow",
            service="payment-service",
            operation="authorize_payment",
            event_type=EventType.SERVICE_COMPLETED,
            latency_ms=-10.0,
        )


def test_workflow_definition_and_execution():
    """Verify WorkflowDefinition and WorkflowExecution models."""
    nodes = [
        WorkflowNode(
            id="n1", name="Auth", node_type=WorkflowNodeType.SERVICE, service_name="auth-service"
        ),
        WorkflowNode(
            id="n2", name="Order", node_type=WorkflowNodeType.SERVICE, service_name="order-service"
        ),
    ]
    edges = [WorkflowEdge(source="n1", target="n2")]

    wf_def = WorkflowDefinition(
        id="order_flow",
        name="Order Flow",
        nodes=nodes,
        edges=edges,
    )
    assert len(wf_def.nodes) == 2
    assert len(wf_def.edges) == 1

    execution = WorkflowExecution(
        workflow_definition_id=wf_def.id,
        status=ExecutionStatus.RUNNING,
    )
    assert execution.id.startswith("exec_")
    assert execution.status == ExecutionStatus.RUNNING


def test_service_definition():
    """Verify ServiceDefinition defaults and bounds."""
    service = ServiceDefinition(
        name="auth-service",
        capacity=150,
        baseline_latency_ms=25.0,
        baseline_failure_rate=0.005,
    )
    assert service.name == "auth-service"
    assert service.baseline_failure_rate == 0.005


def test_incident_model():
    """Verify Incident creation and ground truth fields."""
    incident = Incident(
        scenario_type=IncidentScenario.DATABASE_LATENCY,
        severity=Severity.HIGH,
        affected_services=["database-service", "payment-service"],
        ground_truth_root_cause="Database connection pool starvation",
    )
    assert incident.scenario_type == IncidentScenario.DATABASE_LATENCY
    assert "payment-service" in incident.affected_services


def test_intelligence_models():
    """Verify Prediction, Anomaly, RootCause, and Recommendation models."""
    pred = Prediction(
        execution_id="exec_100",
        model_name="xgboost_v1",
        failure_probability=0.82,
        top_contributions=[
            FeatureContribution(feature_name="payment_latency", value=850.0, contribution=0.45)
        ],
    )
    assert pred.failure_probability == 0.82
    assert len(pred.top_contributions) == 1

    anomaly = Anomaly(
        execution_id="exec_100",
        anomaly_type=AnomalyType.LATENCY_SPIKE,
        score=0.94,
        explanation="Payment latency 5x above baseline",
    )
    assert anomaly.anomaly_type == AnomalyType.LATENCY_SPIKE

    rc = RootCauseHypothesis(
        execution_id="exec_100",
        probable_root_cause="Payment gateway timeout cascade",
        confidence=0.89,
        supporting_evidence=["Payment latency > 2s", "Retry count exceeded 3"],
    )
    assert rc.confidence == 0.89

    rec = Recommendation(
        workflow_id="order_flow",
        current_strategy="sequential_payment",
        recommended_strategy="circuit_breaker_payment_fallback",
        expected_latency_change_ms=-120.0,
        expected_failure_rate_change=-0.15,
    )
    assert rec.expected_failure_rate_change == -0.15
