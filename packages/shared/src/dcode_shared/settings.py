"""Shared application settings — read from env, never hardcoded.

Open Decision placeholders (OD-2 EMBEDDING_*, OD-3 RERANKER_*, OD-4
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
    database_url: str = (
        "postgresql+asyncpg://dcode:__SET_LOCAL_DEV_POSTGRES_PASSWORD__@localhost:5432/dcode"
    )
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = (
        "amqp://dcode:__SET_LOCAL_DEV_RABBITMQ_PASSWORD__@localhost:5672/"
    )

    # --- Logging ---
    log_level: str = "info"

    # --- Internal service auth / cache policy ---
    internal_api_key: str = "__SET_LOCAL_DEV_INTERNAL_API_KEY__"
    query_cache_ttl_seconds: int = 60 * 60
    tool_cache_ttl_seconds: int = 24 * 60 * 60
    job_state_ttl_seconds: int = 7 * 24 * 60 * 60

    # --- Groundedness guardrail (D-2.3.1 / NFR-4) ---
    # The agent redacts any final-answer citation that is not found in the
    # index. Answers scoring below this fraction carry an explicit warning.
    # Must stay > 0 in production so the guardrail cannot be silently disabled.
    groundedness_threshold: float = 0.95

    # --- Open Decisions (OD-2..OD-4) ---
    embedding_model: str = "stub"
    embedding_dim: int = 1024
    embedding_endpoint: str = ""
    embedding_batch_size: int = 4
    embedding_max_retries: int = 12
    # Weighted RRF for hybrid fusion. Dense gets higher weight because
    # equal 1:1 RRF lets sparse keyword noise dilute semantic ranking
    # (observed: B2 dense nDCG > B3 hybrid under equal weights).
    rrf_dense_weight: float = 2.0
    rrf_sparse_weight: float = 1.0
    reranker_model: str = "stub"
    reranker_endpoint: str = ""
    reranker_candidate_limit: int = 16
    reranker_max_retries: int = 3
    judge_model: str = "stub"


shared_settings = SharedSettings()
