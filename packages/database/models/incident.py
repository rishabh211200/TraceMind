"""Ground-truth incident database model."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base, TimestampMixin


class IncidentModel(Base, TimestampMixin):
    """Represents a controlled chaos or production incident ground truth."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, doc="Unique incident ID (e.g. inc_000100_database)"
    )
    scenario_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="DATABASE_LATENCY, PAYMENT_LATENCY_DEGRADATION, etc.",
    )
    severity: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    affected_services: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    ground_truth_root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
