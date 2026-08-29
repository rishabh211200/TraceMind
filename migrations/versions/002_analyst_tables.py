"""002 Analyst Conversations and Messages Tables.

Revision ID: 002_analyst_tables
Revises: 001_initial_schema
Create Date: 2026-08-29 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_analyst_tables"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Analyst Conversations Table
    op.create_table(
        "analyst_conversations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column(
            "title", sa.String(length=255), nullable=False, server_default="New Diagnostic Session"
        ),
        sa.Column("workflow_definition_id", sa.String(length=64), nullable=True),
        sa.Column("execution_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyst_conversations_id", "analyst_conversations", ["id"])
    op.create_index(
        "ix_analyst_conversations_wf_id",
        "analyst_conversations",
        ["workflow_definition_id"],
    )
    op.create_index(
        "ix_analyst_conversations_exec_id",
        "analyst_conversations",
        ["execution_id"],
    )

    # 2. Analyst Messages Table
    op.create_table(
        "analyst_messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("tool_results", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("grounding_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["analyst_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyst_messages_id", "analyst_messages", ["id"])
    op.create_index(
        "ix_analyst_messages_conversation_id",
        "analyst_messages",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_analyst_messages_conversation_id", table_name="analyst_messages")
    op.drop_index("ix_analyst_messages_id", table_name="analyst_messages")
    op.drop_table("analyst_messages")

    op.drop_index("ix_analyst_conversations_exec_id", table_name="analyst_conversations")
    op.drop_index("ix_analyst_conversations_wf_id", table_name="analyst_conversations")
    op.drop_index("ix_analyst_conversations_id", table_name="analyst_conversations")
    op.drop_table("analyst_conversations")
