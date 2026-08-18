"""Service registry and operational baselines database model."""

from typing import Any

from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base, TimestampMixin


class ServiceModel(Base, TimestampMixin):
    """Represents a registered distributed business service or infrastructure component."""

    __tablename__ = "services"

    name: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    service_type: Mapped[str] = mapped_column(
        String(32), default="business_microservice", nullable=False
    )
    capacity: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    baseline_latency_ms: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    baseline_failure_rate: Mapped[float] = mapped_column(Float, default=0.005, nullable=False)
    timeout_ms: Mapped[float] = mapped_column(Float, default=2000.0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    retry_backoff_ms: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    dependencies: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
