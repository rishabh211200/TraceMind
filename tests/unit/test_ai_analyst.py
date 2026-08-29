"""Unit tests for Tool-Grounded Conversational AI Analyst engine, safety limits, and citations."""

import pytest

from apps.ml.analyst.engine import AIAnalystEngine
from apps.ml.analyst.guardrails import (
    CitationGroundingEngine,
    SafetyGuardrail,
    SafetyLimitExceededError,
)
from apps.ml.analyst.llm_client import MockLLMClient
from apps.ml.analyst.models import (
    ChatMessage,
    LLMConfig,
    ToolResult,
)
from apps.ml.analyst.tools import ToolRegistry


@pytest.mark.asyncio
async def test_tool_registry_registration_and_execution():
    """Verify tool registration, schemas, and execution handlers."""
    registry = ToolRegistry()
    defs = registry.get_definitions()
    assert len(defs) >= 6
    names = [d.name for d in defs]
    assert "get_system_topology" in names
    assert "get_root_cause_diagnosis" in names
    assert "get_risk_prediction_and_shap" in names
    assert "get_workflow_optimization" in names

    # Execute system topology tool
    res = await registry.execute_tool("get_system_topology", {"include_health": True})
    assert not res.is_error
    assert isinstance(res.result, dict)
    assert res.result.get("workflow_id") == "order_fulfillment"
    assert res.result.get("system_health") == "OPTIMAL"

    # Execute root cause tool
    rc_res = await registry.execute_tool(
        "get_root_cause_diagnosis", {"execution_id": "exec_test_01"}
    )
    assert not rc_res.is_error
    assert isinstance(rc_res.result, dict)
    assert "primary_culprit" in rc_res.result


@pytest.mark.asyncio
async def test_safety_guardrails():
    """Verify safety limits: max tool calls per turn and mutating keywords block."""
    guardrail = SafetyGuardrail(max_calls_per_turn=5)

    # Valid call counts
    guardrail.validate_tool_call_count(0)
    guardrail.validate_tool_call_count(4)

    # Exceed limit
    with pytest.raises(SafetyLimitExceededError):
        guardrail.validate_tool_call_count(5)

    # Read-only verification
    assert guardrail.validate_read_only("get_trace", {"execution_id": "exec_123"})
    assert not guardrail.validate_read_only("get_trace", {"action": "delete all traces"})
    assert not guardrail.validate_read_only("mutate_service", {"cmd": "restart instance"})


def test_citation_grounding_engine():
    """Verify factual claims extraction, citation injection, and grounding score calculation."""
    engine = CitationGroundingEngine()

    tool_results = [
        ToolResult(
            call_id="call_1",
            name="get_root_cause_diagnosis",
            result={
                "execution_id": "exec_4a9b",
                "primary_culprit": "inventory-db",
                "fault_pattern": "DATABASE_IOPS_SATURATION",
                "confidence_score": 0.98,
            },
            execution_time_ms=1.2,
        ),
        ToolResult(
            call_id="call_2",
            name="get_workflow_optimization",
            result={
                "workflow_definition_id": "order_fulfillment",
                "recommended_path_id": "path_03",
                "recommended_latency_ms": 320.0,
                "latency_reduction_pct": 35.5,
            },
            execution_time_ms=0.8,
        ),
    ]

    # Grounded response referencing tool evidence
    text = (
        "The root cause is inventory-db exhibiting DATABASE_IOPS_SATURATION. "
        "The optimizer recommends path_03 with 320.0ms latency."
    )
    content, report = engine.verify_and_cite(text, tool_results)

    assert report.is_grounded
    assert report.grounding_score >= 0.85
    assert len(report.citations) >= 2
    assert report.verified_claims >= 2


@pytest.mark.asyncio
async def test_mock_llm_client_intent_dispatch():
    """Verify MockLLMClient intent resolution across diagnostic patterns."""
    client = MockLLMClient()
    registry = ToolRegistry()
    tools = registry.get_definitions()
    cfg = LLMConfig(provider="mock")

    # Intent 1: Root Cause
    msg1 = [ChatMessage(role="user", content="Diagnose the root cause of failure in exec_abc123")]
    content, tool_calls = await client.generate_turn(msg1, tools, cfg)
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "get_root_cause_diagnosis"
    assert tool_calls[0].arguments["execution_id"] == "exec_abc123"

    # Intent 2: ML SHAP
    msg2 = [
        ChatMessage(
            role="user",
            content="Show me the SHAP feature attributions and risk probability for exec_999",
        )
    ]
    _, tool_calls2 = await client.generate_turn(msg2, tools, cfg)
    assert len(tool_calls2) == 1
    assert tool_calls2[0].name == "get_risk_prediction_and_shap"

    # Intent 3: Optimizer Detour
    msg3 = [
        ChatMessage(
            role="user",
            content="What detour routing does the optimizer recommend around inventory-db?",
        )
    ]
    _, tool_calls3 = await client.generate_turn(msg3, tools, cfg)
    assert len(tool_calls3) == 1
    assert tool_calls3[0].name == "get_workflow_optimization"
    assert tool_calls3[0].arguments.get("active_incident_culprit") == "inventory-db"


@pytest.mark.asyncio
async def test_ai_analyst_engine_end_to_end_chat():
    """Verify full end-to-end agentic turn with tool execution, synthesis, and citations."""
    engine = AIAnalystEngine()
    response = await engine.chat(
        query="What caused the failure in order_fulfillment execution exec_4a9b?",
        conversation_id="conv_test_100",
    )

    assert response.conversation_id == "conv_test_100"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "get_root_cause_diagnosis"
    assert len(response.tool_results) == 1
    assert not response.tool_results[0].is_error
    assert response.grounding_report.is_grounded
    assert response.grounding_report.grounding_score >= 0.85
    assert len(response.grounding_report.citations) >= 1
    assert "Root Cause Diagnosis" in response.content


@pytest.mark.asyncio
async def test_ai_analyst_engine_streaming():
    """Verify Server-Sent Events streaming chunk generation."""
    engine = AIAnalystEngine()
    chunks: list[dict] = []

    async for chunk in engine.stream_chat(
        query="Explain the ML risk and SHAP attributions for execution exec_4a9b",
        conversation_id="conv_test_stream",
    ):
        chunks.append(chunk)

    chunk_types = [c.get("type") for c in chunks]
    assert "tool_call" in chunk_types
    assert "tool_result" in chunk_types
    assert "token" in chunk_types
    assert "grounding_verified" in chunk_types
    assert "done" in chunk_types
