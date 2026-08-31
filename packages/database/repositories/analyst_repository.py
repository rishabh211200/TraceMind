"""Async repository for conversational AI Analyst session management and message persistence."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.common.logging import get_logger
from packages.database.models.analyst import (
    AnalystConversationModel,
    AnalystMessageModel,
)
from packages.database.models.base import utc_now

logger = get_logger("tracemind.repository.analyst")


class AnalystRepository:
    """Async SQLAlchemy repository for AI Analyst conversations, messages, and citations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_conversation(
        self,
        title: str = "New Diagnostic Session",
        workflow_definition_id: str | None = None,
        execution_id: str | None = None,
        conversation_id: str | None = None,
        tenant_id: str = "tenant_system",
    ) -> AnalystConversationModel:
        """Create and persist a new conversation session."""
        conv = AnalystConversationModel(
            tenant_id=tenant_id,
            title=title,
            workflow_definition_id=workflow_definition_id,
            execution_id=execution_id,
        )
        if conversation_id:
            conv.id = conversation_id

        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        logger.info(
            "analyst_conversation_created",
            conversation_id=conv.id,
            tenant_id=conv.tenant_id,
            title=conv.title,
        )
        return conv

    async def get_conversation(
        self, conversation_id: str, tenant_id: str | None = None
    ) -> AnalystConversationModel | None:
        """Retrieve a conversation with its messages eagerly loaded."""
        stmt = (
            select(AnalystConversationModel)
            .where(AnalystConversationModel.id == conversation_id)
            .options(selectinload(AnalystConversationModel.messages))
        )
        if tenant_id:
            stmt = stmt.where(AnalystConversationModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(
        self,
        workflow_definition_id: str | None = None,
        execution_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> tuple[list[AnalystConversationModel], int]:
        """List conversations with optional filters and total count."""
        stmt = select(AnalystConversationModel)
        count_stmt = select(func.count(AnalystConversationModel.id))

        if tenant_id:
            stmt = stmt.where(AnalystConversationModel.tenant_id == tenant_id)
            count_stmt = count_stmt.where(AnalystConversationModel.tenant_id == tenant_id)

        if workflow_definition_id:
            stmt = stmt.where(
                AnalystConversationModel.workflow_definition_id == workflow_definition_id
            )
            count_stmt = count_stmt.where(
                AnalystConversationModel.workflow_definition_id == workflow_definition_id
            )
        if execution_id:
            stmt = stmt.where(AnalystConversationModel.execution_id == execution_id)
            count_stmt = count_stmt.where(AnalystConversationModel.execution_id == execution_id)

        stmt = (
            stmt.options(selectinload(AnalystConversationModel.messages))
            .order_by(AnalystConversationModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        records = (await self.session.execute(stmt)).scalars().all()
        return list(records), total

    async def delete_conversation(self, conversation_id: str, tenant_id: str | None = None) -> bool:
        """Delete a conversation session and all its associated messages."""
        conv = await self.get_conversation(conversation_id, tenant_id=tenant_id)
        if not conv:
            return False
        await self.session.delete(conv)
        await self.session.commit()
        logger.info("analyst_conversation_deleted", conversation_id=conversation_id)
        return True

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        citations: list[dict[str, Any]] | None = None,
        grounding_score: float = 1.0,
        tenant_id: str = "tenant_system",
    ) -> AnalystMessageModel:
        """Append a message with tool execution metadata and citations to a conversation."""
        msg = AnalystMessageModel(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
            citations=citations or [],
            grounding_score=grounding_score,
        )
        self.session.add(msg)


        # Touch conversation updated_at
        conv_stmt = select(AnalystConversationModel).where(
            AnalystConversationModel.id == conversation_id
        )
        conv = (await self.session.execute(conv_stmt)).scalar_one_or_none()
        if conv:
            conv.updated_at = utc_now()

        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def get_messages(
        self, conversation_id: str, limit: int = 100, offset: int = 0
    ) -> list[AnalystMessageModel]:
        """Retrieve chronological messages for a conversation session."""
        stmt = (
            select(AnalystMessageModel)
            .where(AnalystMessageModel.conversation_id == conversation_id)
            .order_by(AnalystMessageModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        records = (await self.session.execute(stmt)).scalars().all()
        return list(records)

    async def get_stats(self, tenant_id: str | None = None) -> dict[str, Any]:
        """Aggregate platform usage statistics for AI Analyst."""
        c_stmt = select(func.count(AnalystConversationModel.id))
        if tenant_id:
            c_stmt = c_stmt.where(AnalystConversationModel.tenant_id == tenant_id)
        total_convs = (await self.session.execute(c_stmt)).scalar_one()

        m_stmt = select(func.count(AnalystMessageModel.id))
        if tenant_id:
            m_stmt = m_stmt.join(AnalystConversationModel).where(
                AnalystConversationModel.tenant_id == tenant_id
            )
        total_msgs = (await self.session.execute(m_stmt)).scalar_one()

        g_stmt = select(func.avg(AnalystMessageModel.grounding_score))
        if tenant_id:
            g_stmt = g_stmt.join(AnalystConversationModel).where(
                AnalystConversationModel.tenant_id == tenant_id
            )
        avg_grounding = (await self.session.execute(g_stmt)).scalar_one() or 1.0

        return {
            "total_conversations": total_convs,
            "total_messages": total_msgs,
            "average_grounding_score": round(float(avg_grounding), 3),
        }

