"""Embedding clients shared by worker (index-time) and API (query-time).

The same model, ``jinaai/jina-embeddings-v2-base-code``, is reachable two ways:
as a self-hosted sidecar (:class:`HttpEmbeddingClient`) or through Jina AI's
hosted API (:class:`JinaApiEmbeddingClient`). ``EMBEDDING_PROVIDER`` selects
which, and defaults to the sidecar so no existing configuration changes
behaviour. ``EMBEDDING_MODEL=stub`` short-circuits both.

Keeping one model across both paths is deliberate: every evaluation figure this
project displays was measured on that model, so a substitution would make the
displayed numbers describe something other than the running system. See
``Deploy.md`` §2.
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

# Hosted-API defaults. A sidecar can be a model loading on CPU for minutes; an
# API answers in seconds or fails. Applying the sidecar's patience to an API
# turns one bad batch into an hour-long stall behind a prefetch_count=1 worker.
_DEFAULT_API_BATCH_SIZE = 32
_DEFAULT_API_TIMEOUT_SECONDS = 30.0
_DEFAULT_API_MAX_RETRIES = 3

PROVIDER_SIDECAR = "sidecar"
PROVIDER_JINA_API = "jina_api"

# A sidecar we run does not rate-limit us; a hosted API does, and 429 is the
# normal response on a free tier under load. It has to be retryable even though
# every other 4xx must not be.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class EmbeddingClient(ABC):
    """Abstract client for the configured embedding model."""

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


class JinaApiEmbeddingClient(EmbeddingClient):
    """Call Jina AI's hosted ``POST {endpoint}/embeddings``.

    Wire format, observed against the live API on 2026-08-02 rather than taken
    from documentation::

        ->  {"model": "jina-embeddings-v2-base-code", "input": ["a", "b"]}
        <-  {"model": ..., "object": "list",
             "usage": {"total_tokens": 20, "prompt_tokens": 20},
             "data": [{"object": "embedding", "index": 0, "embedding": [...768]}]}

    Two differences from the sidecar contract, and both are load-bearing:

    * the request carries an ``Authorization`` header and a ``model`` field,
      neither of which the sidecar wants;
    * the response identifies each vector by ``index`` instead of returning a
      bare list in input order. Arrival order is not part of the contract, so
      the vectors are placed by index. Trusting arrival order would silently
      attach the wrong embedding to a chunk — a corruption with no error and no
      log line, only worse retrieval.

    The model id is the bare name here, not the Hugging Face ``jinaai/`` path
    the sidecar loads.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str,
        model: str,
        dim: int,
        batch_size: int = _DEFAULT_API_BATCH_SIZE,
        timeout_seconds: float = _DEFAULT_API_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_API_MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = f"{endpoint.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._model = model
        self._dim = dim
        self._batch_size = max(1, batch_size)
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self._max_retries = max(1, max_retries)
        self._transport = transport

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport
        ) as client:
            for start in range(0, len(texts), self._batch_size):
                batch = texts[start : start + self._batch_size]
                payload = await self._post_with_retries(client, batch)
                vectors.extend(self._vectors_in_input_order(payload, len(batch)))
        return vectors

    def _vectors_in_input_order(
        self, payload: dict[str, object], expected: int
    ) -> list[list[float]]:
        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("embedding API returned no 'data' list")
        if len(data) != expected:
            raise RuntimeError(
                f"embedding API returned {len(data)} vectors for {expected} inputs"
            )

        slots: list[list[float] | None] = [None] * expected
        for item in data:
            if not isinstance(item, dict):
                raise RuntimeError("embedding API returned a non-object data item")
            index = item.get("index")
            if not isinstance(index, int) or isinstance(index, bool):
                raise RuntimeError("embedding API returned an item without an integer index")
            if not 0 <= index < expected:
                raise RuntimeError(f"embedding API returned out-of-range index {index}")
            if slots[index] is not None:
                raise RuntimeError(f"embedding API returned duplicate index {index}")
            slots[index] = _validate_vector(item.get("embedding"), self._dim)

        ordered: list[list[float]] = []
        for position, vector in enumerate(slots):
            if vector is None:
                raise RuntimeError(f"embedding API returned no vector for input {position}")
            ordered.append(vector)
        return ordered

    async def _post_with_retries(
        self, client: httpx.AsyncClient, batch: list[str]
    ) -> dict[str, object]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await client.post(
                    self._url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self._model, "input": batch},
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError("embedding API returned invalid JSON payload")
                return payload
            except (
                httpx.RemoteProtocolError,
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.HTTPStatusError,
            ) as exc:
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code not in _RETRYABLE_STATUS
                ):
                    # 401 and 422 do not get better by asking again, and a
                    # wrong key should surface immediately rather than after
                    # three backoffs.
                    raise
                last_error = exc
                if attempt >= self._max_retries - 1:
                    break
                delay = min(30.0, 2.0 * (2**attempt))
                logger.warning(
                    "embedding API request failed (attempt %s/%s), retrying in %.0fs: %s",
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
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    provider: str = PROVIDER_SIDECAR,
    api_key: str = "",
) -> EmbeddingClient:
    """Build the embedding client for the current environment.

    ``provider`` defaults to the sidecar, so an environment that predates
    ``EMBEDDING_PROVIDER`` keeps exactly its current behaviour.
    """
    if model == "stub":
        return StubEmbeddingClient(dim=dim)

    normalized_endpoint = endpoint.strip()
    if not normalized_endpoint:
        raise ValueError(
            "EMBEDDING_ENDPOINT is required when EMBEDDING_MODEL is not 'stub'"
        )

    normalized_provider = provider.strip().lower() or PROVIDER_SIDECAR

    if normalized_provider == PROVIDER_SIDECAR:
        logger.info(
            "using HTTP embedding client model=%s endpoint=%s", model, normalized_endpoint
        )
        return HttpEmbeddingClient(
            normalized_endpoint,
            dim=dim,
            batch_size=batch_size,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    if normalized_provider == PROVIDER_JINA_API:
        if not api_key.strip():
            raise ValueError(
                f"EMBEDDING_API_KEY is required when EMBEDDING_PROVIDER is "
                f"'{PROVIDER_JINA_API}'"
            )
        logger.info(
            "using Jina API embedding client model=%s endpoint=%s", model, normalized_endpoint
        )
        return JinaApiEmbeddingClient(
            normalized_endpoint,
            api_key=api_key.strip(),
            model=model,
            dim=dim,
            batch_size=batch_size,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    raise ValueError(
        f"unknown EMBEDDING_PROVIDER {provider!r}; "
        f"expected one of {PROVIDER_SIDECAR!r}, {PROVIDER_JINA_API!r}"
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
