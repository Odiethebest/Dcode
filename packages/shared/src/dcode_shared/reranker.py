"""Reranker clients for hybrid retrieval (OD-3).

``BAAI/bge-reranker-v2-m3`` is hosted as a sidecar HTTP service;
the API calls it through :class:`HttpRerankerClient`.
``RERANKER_MODEL=stub`` keeps identity rerank (fused-score order).
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 120.0
_DEFAULT_MAX_RETRIES = 12


class RerankerClient(ABC):
    """Abstract cross-encoder reranker client (OD-3)."""

    @abstractmethod
    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        """Return one relevance score per passage, in input order."""


class HttpRerankerClient(RerankerClient):
    """Call a sidecar ``POST /rerank`` endpoint that scores query-passage pairs."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self._max_retries = max_retries

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []

        payload = await self._post_rerank_with_retries(query, passages)
        scores = payload.get("scores")
        if not isinstance(scores, list):
            raise RuntimeError("reranker service returned invalid scores payload")
        if len(scores) != len(passages):
            raise RuntimeError(
                "reranker service returned a different number of scores than passages"
            )
        return [_validate_score(score) for score in scores]

    async def _post_rerank_with_retries(
        self,
        query: str,
        passages: list[str],
    ) -> dict[str, object]:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(self._max_retries):
                try:
                    response = await client.post(
                        f"{self._endpoint}/rerank",
                        json={"query": query, "passages": passages},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise RuntimeError("reranker service returned invalid JSON payload")
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
                        "reranker request failed (attempt %s/%s), retrying in %.0fs: %s",
                        attempt + 1,
                        self._max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error


def create_reranker_client(
    *,
    model: str,
    endpoint: str = "",
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> RerankerClient | None:
    """Build the reranker client for the current environment.

    Returns ``None`` when ``model`` is ``stub`` so callers keep identity rerank.
    """
    if model == "stub":
        return None

    normalized_endpoint = endpoint.strip()
    if not normalized_endpoint:
        raise ValueError("RERANKER_ENDPOINT is required when RERANKER_MODEL is not 'stub'")

    logger.info("using HTTP reranker client model=%s endpoint=%s", model, normalized_endpoint)
    return HttpRerankerClient(normalized_endpoint, max_retries=max_retries)


def _validate_score(score: object) -> float:
    if not isinstance(score, int | float):
        raise ValueError("reranker score must be numeric")
    return float(score)
