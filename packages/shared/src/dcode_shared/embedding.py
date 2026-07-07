"""Embedding clients shared by worker (index-time) and API (query-time).

Open Decision OD-2: ``jinaai/jina-embeddings-v2-base-code`` is hosted as a
sidecar HTTP service; worker/API call it through :class:`HttpEmbeddingClient`.
``EMBEDDING_MODEL=stub`` keeps local development working without the sidecar.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 4
_DEFAULT_TIMEOUT_SECONDS = 300.0
_DEFAULT_MAX_RETRIES = 12


class EmbeddingClient(ABC):
    """Abstract client for the configured embedding model (OD-2)."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text. Caller-driven batching."""


class StubEmbeddingClient(EmbeddingClient):
    """Placeholder — returns zero vectors of the configured dimension."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]


class HttpEmbeddingClient(EmbeddingClient):
    """Call a sidecar ``POST /embed`` endpoint that returns dense vectors."""

    def __init__(
        self,
        endpoint: str,
        *,
        dim: int,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._dim = dim
        self._batch_size = batch_size
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self._max_retries = max_retries

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(texts), self._batch_size):
                batch = texts[start : start + self._batch_size]
                payload = await self._post_embed_with_retries(client, batch)
                batch_vectors = payload.get("embeddings")
                if not isinstance(batch_vectors, list):
                    raise RuntimeError("embedding service returned invalid embeddings payload")
                if len(batch_vectors) != len(batch):
                    raise RuntimeError(
                        "embedding service returned a different number of vectors than inputs"
                    )
                for vector in batch_vectors:
                    vectors.append(_validate_vector(vector, self._dim))
        return vectors

    async def _post_embed_with_retries(
        self,
        client: httpx.AsyncClient,
        batch: list[str],
    ) -> dict[str, object]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await client.post(
                    f"{self._endpoint}/embed",
                    json={"texts": batch},
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError("embedding service returned invalid JSON payload")
                return payload
            except (
                httpx.RemoteProtocolError,
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.HTTPStatusError,
            ) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
                last_error = exc
                if attempt >= self._max_retries - 1:
                    break
                delay = min(30.0, 2.0 * (2**attempt))
                logger.warning(
                    "embedding request failed (attempt %s/%s), retrying in %.0fs: %s",
                    attempt + 1,
                    self._max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error


def create_embedding_client(
    *,
    model: str,
    dim: int,
    endpoint: str = "",
    batch_size: int = _DEFAULT_BATCH_SIZE,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> EmbeddingClient:
    """Build the embedding client for the current environment."""
    if model == "stub":
        return StubEmbeddingClient(dim=dim)

    normalized_endpoint = endpoint.strip()
    if not normalized_endpoint:
        raise ValueError(
            "EMBEDDING_ENDPOINT is required when EMBEDDING_MODEL is not 'stub'"
        )

    logger.info("using HTTP embedding client model=%s endpoint=%s", model, normalized_endpoint)
    return HttpEmbeddingClient(
        normalized_endpoint,
        dim=dim,
        batch_size=batch_size,
        max_retries=max_retries,
    )


def _validate_vector(vector: object, embedding_dim: int) -> list[float]:
    if not isinstance(vector, list):
        raise ValueError("embedding vector must be a list")

    if len(vector) != embedding_dim:
        raise ValueError(
            f"embedding dimension mismatch: expected {embedding_dim}, got {len(vector)}"
        )

    values: list[float] = []
    for value in vector:
        if not isinstance(value, int | float):
            raise ValueError("embedding vector contains a non-numeric value")
        values.append(float(value))
    return values
