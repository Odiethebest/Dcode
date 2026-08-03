"""Shared application settings — read from env, never hardcoded.

Embedding, reranker, judge, cache, and infrastructure settings live here so
every service reads them uniformly.
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

    # --- Groundedness guardrail ---
    # The agent redacts any final-answer citation that is not found in the
    # index. Answers scoring below this fraction carry an explicit warning.
    # Must stay > 0 in production so the guardrail cannot be silently disabled.
    groundedness_threshold: float = 0.95

    # --- Retrieval and evaluation models ---
    # `provider` selects HOW a model is reached, never WHICH model runs. Both
    # paths serve the same weights, which is what keeps the displayed
    # evaluation figures a description of the deployed system (Deploy.md §2).
    # Default `sidecar` so configuration written before these existed is
    # unaffected.
    embedding_provider: str = "sidecar"
    embedding_api_key: str = ""
    reranker_provider: str = "sidecar"
    reranker_api_key: str = ""
    embedding_model: str = "stub"
    embedding_dim: int = 1024
    embedding_endpoint: str = ""
    embedding_batch_size: int = 4
    # The defaults below are sized for a cold self-hosted sidecar: a CPU Jina
    # model can take minutes to load, and the retries exist to ride that out.
    # Their product is the worst case, and it is long — 12 attempts against a
    # 300s read timeout can hold one batch for about an hour while the worker
    # (prefetch_count=1) stalls every other queued repository behind it. A
    # hosted embedding API fails in seconds and should be configured with much
    # smaller values; both are env-tunable so neither path pays the other's cost.
    embedding_max_retries: int = 12
    embedding_timeout_seconds: float = 300.0
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
