"""Application configuration powered by pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for TraceMind services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General
    environment: str = Field(default="development", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Logging verbosity")
    debug: bool = Field(default=False, description="Debug mode flag")

    # API Server
    api_host: str = Field(default="0.0.0.0", description="API listen host")
    api_port: int = Field(default=8000, description="API listen port")
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Persistence
    database_url: str = Field(
        default="postgresql+asyncpg://tracemind:tracemind_secret@localhost:5432/tracemind_db",
        description="Async SQLAlchemy database connection URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and temporary state",
    )

    # Event Streaming
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap brokers",
    )
    kafka_topic_traces: str = Field(
        default="tracemind.events.raw",
        description="Raw trace events topic",
    )
    kafka_topic_anomalies: str = Field(
        default="tracemind.events.anomalies",
        description="Detected anomalies event topic",
    )
    kafka_consumer_group: str = Field(
        default="tracemind-ingestor",
        description="Default consumer group for streaming ingestion worker",
    )
    kafka_batch_size: int = Field(
        default=1000,
        description="Max micro-batch size before triggering database flush",
    )
    kafka_flush_interval_ms: int = Field(
        default=50,
        description="Max wait time (ms) before flushing pending micro-batch to database",
    )
    kafka_auto_offset_reset: str = Field(
        default="earliest",
        description="Offset reset policy ('earliest', 'latest')",
    )

    # Simulator Defaults
    simulator_default_seed: int = Field(default=42, description="Default pseudo-random seed")
    simulator_default_workflow_count: int = Field(
        default=1000, description="Default trace batch size"
    )
    simulator_incident_probability: float = Field(
        default=0.05, description="Synthetic incident injection rate"
    )

    # MLflow Tracking
    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000", description="MLflow experiment server URI"
    )
    mlflow_experiment_name: str = Field(
        default="tracemind-failure-prediction", description="Default experiment name"
    )

    # AI Analyst
    ai_provider: str = Field(
        default="openai", description="AI provider (openai, anthropic, gemini, local)"
    )
    ai_model_name: str = Field(default="gpt-4o-mini", description="Target LLM model name")
    ai_api_key: str = Field(default="", description="Provider API key")
    ai_temperature: float = Field(default=0.1, description="Sampling temperature")


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
