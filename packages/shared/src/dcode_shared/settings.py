"""Shared application settings — read from env, never hardcoded.

Open Decision placeholders (OD-2 EMBEDDING_*, OD-3 RERANKER_ENDPOINT, OD-4
JUDGE_MODEL) live here so every service reads them uniformly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedSettings(BaseSettings):
    """Base settings every Dcode Python service inherits or composes."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Infrastructure ---
    database_url: str = "postgresql+asyncpg://dcode:dcode@localhost:5432/dcode"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    # --- Logging ---
    log_level: str = "info"

    # --- Internal service auth / cache policy ---
    internal_api_key: str = "dev-internal-key-change-me"
    query_cache_ttl_seconds: int = 60 * 60
    tool_cache_ttl_seconds: int = 24 * 60 * 60
    job_state_ttl_seconds: int = 7 * 24 * 60 * 60

    # --- Open Decisions (OD-2..OD-4) ---
    embedding_model: str = "stub"
    embedding_dim: int = 1024
    reranker_endpoint: str = "http://localhost:9999"
    judge_model: str = "stub"


shared_settings = SharedSettings()
