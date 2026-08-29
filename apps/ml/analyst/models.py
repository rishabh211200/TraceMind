"""Domain models and data structures for the Tool-Grounded Conversational AI Analyst."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4


@dataclass
class ToolCall:
    """Represents a structured tool execution request from the LLM."""

    id: str = field(default_factory=lambda: f"call_{uuid4().hex[:8]}")
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Represents the output resulting from executing a platform tool."""

    call_id: str
    name: str
    result: dict[str, Any] | list[Any] | str
    execution_time_ms: float = 0.0
    is_error: bool = False
    error_message: str | None = None


@dataclass
class Citation:
    """Structured citation linking a factual statement to verified tool evidence."""

    citation_id: int
    tool_name: str
    entity_id: str
    field_name: str
    verified_value: str | float | int | bool
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize citation to dictionary."""
        return {
            "citation_id": self.citation_id,
            "tool_name": self.tool_name,
            "entity_id": self.entity_id,
            "field_name": self.field_name,
            "verified_value": self.verified_value,
            "snippet": self.snippet,
        }


@dataclass
class GroundingReport:
    """Verification report evaluating the factual fidelity of the generated response."""

    is_grounded: bool = True
    grounding_score: float = 1.0  # 0.0 to 1.0
    total_claims: int = 0
    verified_claims: int = 0
    unverified_claims: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize grounding report to dictionary."""
        return {
            "is_grounded": self.is_grounded,
            "grounding_score": round(self.grounding_score, 3),
            "total_claims": self.total_claims,
            "verified_claims": self.verified_claims,
            "unverified_claims": self.unverified_claims,
            "citations": [c.to_dict() for c in self.citations],
        }


@dataclass
class ChatMessage:
    """Represents a conversational message in an Analyst session."""

    id: str = field(default_factory=lambda: f"msg_{uuid4().hex[:8]}")
    role: Literal["user", "assistant", "system", "tool"] = "user"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    grounding_score: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize message to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in self.tool_calls
            ],
            "tool_results": [
                {
                    "call_id": tr.call_id,
                    "name": tr.name,
                    "result": tr.result,
                    "execution_time_ms": tr.execution_time_ms,
                    "is_error": tr.is_error,
                }
                for tr in self.tool_results
            ],
            "citations": [c.to_dict() for c in self.citations],
            "grounding_score": round(self.grounding_score, 3),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ToolDefinition:
    """JSON Schema definition for an LLM-invocable platform tool."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_schema(self) -> dict[str, Any]:
        """Generate OpenAI/Anthropic/Gemini compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class LLMConfig:
    """Runtime configuration for LLM generation."""

    provider: Literal["mock", "openai", "anthropic", "gemini"] = "mock"
    model_name: str = "tracemind-deterministic-analyst"
    temperature: float = 0.0
    api_key: str | None = None
    max_tokens: int = 2048


@dataclass
class AnalystResponse:
    """Complete response payload produced by AIAnalystEngine."""

    conversation_id: str
    message_id: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    grounding_report: GroundingReport = field(default_factory=GroundingReport)
    execution_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete response to dictionary."""
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "content": self.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in self.tool_calls
            ],
            "tool_results": [
                {
                    "call_id": tr.call_id,
                    "name": tr.name,
                    "result": tr.result,
                    "execution_time_ms": tr.execution_time_ms,
                    "is_error": tr.is_error,
                }
                for tr in self.tool_results
            ],
            "grounding_report": self.grounding_report.to_dict(),
            "execution_latency_ms": round(self.execution_latency_ms, 2),
        }
