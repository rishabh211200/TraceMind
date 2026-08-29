"""Database ORM models for conversational AI Analyst sessions, messages, and tool invocations."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.database.models.base import Base, utc_now


class AnalystConversationModel(Base):
    """Represents a persistent multi-turn diagnostic conversation session."""

    __tablename__ = "analyst_conversations"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"conv_{uuid4().hex[:10]}",
        doc="Unique conversation session identifier (e.g. conv_a1b2c3d4)",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Diagnostic Session",
        doc="Human-readable title summarizing the conversation session",
    )
    workflow_definition_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="Optional workflow definition context (e.g. order_fulfillment)",
    )
    execution_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="Optional target workflow execution context (e.g. exec_4a9b)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        doc="Timestamp when conversation session was initialized",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        doc="Timestamp of the latest message activity",
    )

    messages: Mapped[list["AnalystMessageModel"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AnalystMessageModel.created_at",
        lazy="selectin",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert conversation model to serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "workflow_definition_id": self.workflow_definition_id,
            "execution_id": self.execution_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }


class AnalystMessageModel(Base):
    """Represents a single message in an Analyst conversation with tool calls and citations."""

    __tablename__ = "analyst_messages"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"msg_{uuid4().hex[:10]}",
        doc="Unique message identifier (e.g. msg_x1y2z3)",
    )
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("analyst_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent conversation",
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Message author role ('user', 'assistant', 'system', 'tool')",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        doc="Textual content of the message",
    )
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        doc="List of tool calls executed during generation",
    )
    tool_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        doc="List of tool results returned from platform modules",
    )
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        doc="List of structured citations linking claims to evidence",
    )
    grounding_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        doc="Confidence score (0.0 - 1.0) indicating factual grounding against tool evidence",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        doc="Timestamp when message was posted",
    )

    conversation: Mapped["AnalystConversationModel"] = relationship(back_populates="messages")

    def to_dict(self) -> dict[str, Any]:
        """Convert message model to serializable dictionary."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls or [],
            "tool_results": self.tool_results or [],
            "citations": self.citations or [],
            "grounding_score": self.grounding_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
