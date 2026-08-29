"""AIAnalystEngine coordinating multi-turn conversations, tool executions, and citation-level grounding."""

import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from apps.ml.analyst.guardrails import CitationGroundingEngine, SafetyGuardrail
from apps.ml.analyst.llm_client import BaseLLMClient, MockLLMClient
from apps.ml.analyst.models import (
    AnalystResponse,
    ChatMessage,
    LLMConfig,
    ToolCall,
    ToolResult,
)
from apps.ml.analyst.tools import ToolRegistry
from packages.common.logging import get_logger

logger = get_logger("tracemind.analyst.engine")


class AIAnalystEngine:
    """Core Tool-Grounded Conversational AI Analyst engine."""

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        llm_client: BaseLLMClient | None = None,
        guardrail: SafetyGuardrail | None = None,
        grounding_engine: CitationGroundingEngine | None = None,
        default_config: LLMConfig | None = None,
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry()
        self.llm_client = llm_client or MockLLMClient()
        self.guardrail = guardrail or SafetyGuardrail()
        self.grounding_engine = grounding_engine or CitationGroundingEngine()
        self.default_config = default_config or LLMConfig()

    async def chat(
        self,
        query: str,
        history: list[ChatMessage] | None = None,
        conversation_id: str | None = None,
        config: LLMConfig | None = None,
    ) -> AnalystResponse:
        """Process a user query through the agentic tool-execution loop and return a grounded response."""
        start_time = time.perf_counter()
        conv_id = conversation_id or f"conv_{uuid4().hex[:10]}"
        cfg = config or self.default_config

        messages: list[ChatMessage] = list(history or [])
        user_msg = ChatMessage(role="user", content=query)
        messages.append(user_msg)

        all_tool_calls: list[ToolCall] = []
        all_tool_results: list[ToolResult] = []
        tool_call_count = 0

        # Agent ReAct / Tool-Calling Loop (up to safety limit)
        while tool_call_count < self.guardrail.max_calls_per_turn:
            tools_schema = self.tool_registry.get_definitions()
            content, tool_calls = await self.llm_client.generate_turn(
                messages=messages,
                tools=tools_schema,
                config=cfg,
            )

            if not tool_calls:
                # LLM produced final response
                break

            # Execute requested tool calls
            for tc in tool_calls:
                self.guardrail.validate_tool_call_count(tool_call_count)
                if not self.guardrail.validate_read_only(tc.name, tc.arguments):
                    tr = ToolResult(
                        call_id=tc.id,
                        name=tc.name,
                        result="Error: Write or mutating action blocked by safety guardrail.",
                        is_error=True,
                    )
                else:
                    tr = await self.tool_registry.execute_tool(
                        name=tc.name,
                        arguments=tc.arguments,
                        call_id=tc.id,
                    )

                all_tool_calls.append(tc)
                all_tool_results.append(tr)
                tool_call_count += 1

                # Append tool result to conversation history
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=str(tr.result),
                        tool_calls=[tc],
                        tool_results=[tr],
                    )
                )

        # Grounding & Citation Verification
        grounded_content, grounding_report = self.grounding_engine.verify_and_cite(
            content=content,
            tool_results=all_tool_results,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        msg_id = f"msg_{uuid4().hex[:10]}"

        logger.info(
            "analyst_chat_completed",
            conversation_id=conv_id,
            tool_calls=len(all_tool_calls),
            grounding_score=grounding_report.grounding_score,
            latency_ms=elapsed_ms,
        )

        return AnalystResponse(
            conversation_id=conv_id,
            message_id=msg_id,
            content=grounded_content,
            tool_calls=all_tool_calls,
            tool_results=all_tool_results,
            grounding_report=grounding_report,
            execution_latency_ms=round(elapsed_ms, 2),
        )

    async def stream_chat(
        self,
        query: str,
        history: list[ChatMessage] | None = None,
        conversation_id: str | None = None,
        config: LLMConfig | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream conversational chunks, tool execution signals, and grounding reports."""
        start_time = time.perf_counter()
        conv_id = conversation_id or f"conv_{uuid4().hex[:10]}"
        cfg = config or self.default_config

        messages: list[ChatMessage] = list(history or [])
        user_msg = ChatMessage(role="user", content=query)
        messages.append(user_msg)

        all_tool_calls: list[ToolCall] = []
        all_tool_results: list[ToolResult] = []
        tool_call_count = 0

        # Step 1: Check if tool calling is required
        tools_schema = self.tool_registry.get_definitions()
        content, tool_calls = await self.llm_client.generate_turn(
            messages=messages,
            tools=tools_schema,
            config=cfg,
        )

        if tool_calls:
            for tc in tool_calls:
                yield {
                    "type": "tool_call",
                    "tool_call": {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    },
                }

                tr = await self.tool_registry.execute_tool(
                    name=tc.name,
                    arguments=tc.arguments,
                    call_id=tc.id,
                )
                all_tool_calls.append(tc)
                all_tool_results.append(tr)
                tool_call_count += 1

                yield {
                    "type": "tool_result",
                    "tool_result": {
                        "call_id": tr.call_id,
                        "name": tr.name,
                        "result": tr.result,
                        "execution_time_ms": tr.execution_time_ms,
                        "is_error": tr.is_error,
                    },
                }

                messages.append(
                    ChatMessage(
                        role="tool",
                        content=str(tr.result),
                        tool_calls=[tc],
                        tool_results=[tr],
                    )
                )

            # Re-generate synthesis
            content, _ = await self.llm_client.generate_turn(
                messages=messages,
                tools=tools_schema,
                config=cfg,
            )

        # Step 2: Grounding & Citation Verification
        grounded_content, grounding_report = self.grounding_engine.verify_and_cite(
            content=content,
            tool_results=all_tool_results,
        )

        # Step 3: Stream tokens
        words = grounded_content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield {"type": "token", "token": chunk}

        # Step 4: Emit Grounding verification report and completion
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        yield {
            "type": "grounding_verified",
            "grounding_report": grounding_report.to_dict(),
            "execution_latency_ms": round(elapsed_ms, 2),
            "conversation_id": conv_id,
        }
        yield {"type": "done"}
