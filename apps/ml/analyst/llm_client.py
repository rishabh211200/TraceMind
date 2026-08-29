"""Provider-agnostic LLM client abstraction and deterministic local mock engine."""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from apps.ml.analyst.models import (
    ChatMessage,
    LLMConfig,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from packages.common.logging import get_logger

logger = get_logger("tracemind.analyst.llm_client")


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_turn(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        config: LLMConfig,
    ) -> tuple[str, list[ToolCall]]:
        """Generate response text or tool calls for a conversation turn."""

    @abstractmethod
    def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        config: LLMConfig,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream token chunks or tool execution signals."""


class MockLLMClient(BaseLLMClient):
    """Deterministic, offline rule-based agent for test environments and local development."""

    def _classify_intent_and_tools(
        self, user_content: str, exec_id: str
    ) -> tuple[str, list[ToolCall]]:
        """Map user natural language query to appropriate platform tool calls."""
        # 1. Root Cause / Failure Diagnosis
        if any(
            kw in user_content
            for kw in [
                "root cause",
                "diagnose",
                "why did",
                "failed",
                "failure",
                "cause",
                "culprit",
                "incident",
                "error",
                "outage",
            ]
        ):
            return (
                "Let me run deterministic causal graph reasoning to identify the root cause of this execution.",
                [ToolCall(name="get_root_cause_diagnosis", arguments={"execution_id": exec_id})],
            )

        # 2. ML Risk & SHAP Attributions
        if any(
            kw in user_content
            for kw in ["shap", "risk", "prediction", "probability", "feature importance"]
        ):
            return (
                "Querying in-flight ML risk predictor and TreeSHAP feature attributions...",
                [
                    ToolCall(
                        name="get_risk_prediction_and_shap", arguments={"execution_id": exec_id}
                    )
                ],
            )

        # 3. Workflow Optimization / Routing / Cost
        if any(
            kw in user_content
            for kw in [
                "optimize",
                "optimizer",
                "route",
                "routing",
                "pareto",
                "detour",
                "cost",
                "bypass",
            ]
        ):
            culprit = next(
                (
                    svc
                    for svc in ["inventory-db", "customer-db", "payment-gateway", "pricing-service"]
                    if svc in user_content
                ),
                None,
            )
            return (
                "Calculating 3D Pareto optimal routing paths and transparent resource cost models...",
                [
                    ToolCall(
                        name="get_workflow_optimization",
                        arguments={
                            "workflow_definition_id": "order_fulfillment",
                            "active_incident_culprit": culprit,
                        },
                    )
                ],
            )

        # 4. Anomalies
        if any(
            kw in user_content for kw in ["anomaly", "anomalies", "outlier", "unusual", "spike"]
        ):
            return (
                "Querying multi-model unsupervised anomaly detection scores...",
                [ToolCall(name="get_anomalies", arguments={"execution_id": exec_id})],
            )

        # 5. System Topology / Health
        if any(
            kw in user_content
            for kw in ["topology", "services", "health", "system", "architecture", "dependencies"]
        ):
            return (
                "Retrieving system microservice dependency topology and operational health...",
                [ToolCall(name="get_system_topology", arguments={"include_health": True})],
            )

        # 6. Trace Tree Spans
        if any(kw in user_content for kw in ["trace", "spans", "waterfall", "dag", "timeline"]):
            return (
                f"Fetching execution span tree DAG for execution `{exec_id}`...",
                [ToolCall(name="get_trace_tree", arguments={"execution_id": exec_id})],
            )

        return (
            f"I have inspected your query regarding `{exec_id}`. I can run deterministic root cause diagnosis, "
            "evaluate TreeSHAP risk factors, calculate 3D Pareto optimal routing detours, or query system topology. "
            "How would you like to proceed?",
            [],
        )

    async def generate_turn(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        config: LLMConfig,
    ) -> tuple[str, list[ToolCall]]:
        """Interpret user query, decide on tool calls, or synthesize final grounded response."""
        if not messages:
            return (
                "Hello! I am your TraceMind AI Analyst. How can I assist you with distributed workflow diagnostics today?",
                [],
            )

        last_msg = messages[-1]

        # Case 1: The last message was a tool result -> synthesize grounded explanation
        if last_msg.role == "tool" or (last_msg.tool_results and len(last_msg.tool_results) > 0):
            return self._synthesize_tool_response(messages), []

        user_content = last_msg.content.lower()

        # Extract execution ID if present
        exec_match = re.search(r"exec_[a-zA-Z0-9_-]+", user_content)
        exec_id = exec_match.group(0) if exec_match else "exec_4a9b"

        return self._classify_intent_and_tools(user_content, exec_id)

    def _synthesize_tool_response(self, messages: list[ChatMessage]) -> str:
        """Construct a structured, professional markdown diagnostic response based on tool results."""
        tool_results: list[ToolResult] = []
        for msg in messages:
            tool_results.extend(msg.tool_results)

        if not tool_results:
            return "Analysis complete based on platform telemetry."

        sections: list[str] = []

        for tr in tool_results:
            res = tr.result
            if not isinstance(res, dict):
                continue

            if tr.name == "get_root_cause_diagnosis":
                culprit = res.get("primary_culprit", "unknown-service")
                pattern = res.get("fault_pattern", "GENERIC_FAILURE")
                confidence = float(res.get("confidence_score", 0.95)) * 100
                summary = res.get("summary", "Root cause identified.")
                chain = res.get("propagation_chain", [])
                chain_str = (
                    " -> ".join([f"`{c.get('service')}`" for c in chain])
                    if chain
                    else f"`{culprit}`"
                )

                sections.append(
                    f"### 🔍 Root Cause Diagnosis\n\n"
                    f"* **Primary Culprit**: `{culprit}`\n"
                    f"* **Fault Pattern**: `{pattern}`\n"
                    f"* **Diagnostic Confidence**: `{confidence:.1f}%`\n"
                    f"* **Causal Propagation Path**: {chain_str}\n\n"
                    f"**Executive Briefing**: {summary}"
                )

            elif tr.name == "get_risk_prediction_and_shap":
                prob = float(res.get("predicted_failure_probability", 0.0)) * 100
                risk_lvl = res.get("predicted_risk_level", "LOW")
                shaps = res.get("shap_attributions", [])
                shap_bullets = "\n".join(
                    [
                        f"  * `{s.get('feature')}`: SHAP value `+{s.get('shap_value')}` ({s.get('importance')} importance)"
                        for s in shaps[:3]
                    ]
                )

                sections.append(
                    f"### 📊 Machine Learning Failure Risk & SHAP Attributions\n\n"
                    f"* **Predicted Failure Probability**: `{prob:.1f}%` (`{risk_lvl}`)\n"
                    f"* **Key Feature Drivers**:\n{shap_bullets}"
                )

            elif tr.name == "get_workflow_optimization":
                rec_path = res.get("recommended_path_id", "path_01")
                lat_ms = res.get("recommended_latency_ms", 350.0)
                cost_u = res.get("recommended_cost_units", 10.0)
                rel = float(res.get("recommended_reliability", 0.98)) * 100
                lat_red = res.get("latency_reduction_pct", 0.0)
                culprit = res.get("active_incident_culprit")
                rationale = res.get("rationale", "")

                diversion_note = f" (Advisory Detour around `{culprit}`)" if culprit else ""
                sections.append(
                    f"### ⚡ Workflow Optimizer Recommendation{diversion_note}\n\n"
                    f"* **Recommended Optimal Route**: `{rec_path}`\n"
                    f"* **Projected Latency**: `{lat_ms}ms` ({lat_red:.1f}% reduction)\n"
                    f"* **Modeled Resource Cost**: `{cost_u}u`\n"
                    f"* **Projected Reliability**: `{rel:.1f}%`\n\n"
                    f"**Optimization Rationale**: {rationale}"
                )

            elif tr.name == "get_system_topology":
                tot = res.get("total_services", 0)
                health = res.get("system_health", "OPTIMAL")
                sections.append(
                    f"### 🌐 System Topology Overview\n\n"
                    f"* **Total Managed Microservices**: `{tot}`\n"
                    f"* **System Operational Status**: `{health}`\n"
                    f"* **Primary Services**: `api-gateway`, `auth-service`, `customer-service`, `inventory-service`, `payment-service`, `order-service`."
                )

            elif tr.name == "get_anomalies":
                is_anom = res.get("is_anomalous", False)
                score = res.get("composite_anomaly_score", 0.0)
                status_str = "ANOMALOUS" if is_anom else "NORMAL"
                sections.append(
                    f"### 🚨 Unsupervised Anomaly Detection\n\n"
                    f"* **Anomaly Status**: `{status_str}` (Score: `{score:.2f}`)\n"
                    f"* **Isolation Forest**: `{res.get('detector_scores', {}).get('isolation_forest', 0.0):.2f}`\n"
                    f"* **Autoencoder**: `{res.get('detector_scores', {}).get('autoencoder', 0.0):.2f}`"
                )

        return "\n\n---\n\n".join(sections) if sections else "Analysis complete."

    async def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        config: LLMConfig,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chunks of the response."""
        content, tool_calls = await self.generate_turn(messages, tools, config)
        if tool_calls:
            for tc in tool_calls:
                yield {
                    "type": "tool_call",
                    "tool_call": {"id": tc.id, "name": tc.name, "arguments": tc.arguments},
                }
            return

        # Simulate streaming by yielding tokens
        words = content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield {"type": "token", "token": chunk}
            await asyncio.sleep(0.01)

        yield {"type": "done"}


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API integration for tool-calling models."""

    def __init__(
        self, api_key: str | None = None, base_url: str = "https://api.openai.com/v1"
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url

    async def generate_turn(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        config: LLMConfig,
    ) -> tuple[str, list[ToolCall]]:
        """Call OpenAI chat completions API."""
        api_key = config.api_key or self.api_key
        if not api_key:
            # Fall back gracefully to deterministic mock if API key is missing
            return await MockLLMClient().generate_turn(messages, tools, config)

        formatted_msgs = [{"role": m.role, "content": m.content} for m in messages]
        formatted_tools = [t.to_schema() for t in tools]

        payload: dict[str, Any] = {
            "model": config.model_name or "gpt-4o",
            "messages": formatted_msgs,
            "temperature": config.temperature,
        }
        if formatted_tools:
            payload["tools"] = formatted_tools

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            data = resp.json()
            choice = data["choices"][0]["message"]
            content = choice.get("content") or ""
            raw_tcs = choice.get("tool_calls") or []
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"].get("arguments", "{}")),
                )
                for tc in raw_tcs
            ]
            return content, tool_calls

    async def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        config: LLMConfig,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream OpenAI response."""
        content, tool_calls = await self.generate_turn(messages, tools, config)
        if tool_calls:
            for tc in tool_calls:
                yield {
                    "type": "tool_call",
                    "tool_call": {"id": tc.id, "name": tc.name, "arguments": tc.arguments},
                }
        else:
            for word in content.split(" "):
                yield {"type": "token", "token": word + " "}
                await asyncio.sleep(0.01)
        yield {"type": "done"}
