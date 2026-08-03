"""Reranker clients for hybrid retrieval.

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

# Query-time rerank must stay interactive: a bounded read timeout (then fail
# fast and let the caller degrade to fused order) and few retries. Retries cover
# a still-warming model server (ConnectError), NOT slow inference (ReadTimeout) —
# retrying a slow CPU rerank just piles duplicate work onto a single-threaded
# model server and makes everything slower.
_DEFAULT_TIMEOUT_SECONDS = 20.0
_DEFAULT_MAX_RETRIES = 3

PROVIDER_SIDECAR = "sidecar"
PROVIDER_SILICONFLOW = "siliconflow"

# A hosted API rate-limits; a sidecar we run does not. 429 has to be retryable
# even though every other 4xx must not be.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class RerankerClient(ABC):
    """Abstract cross-encoder reranker client."""

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


class SiliconFlowRerankerClient(RerankerClient):
    """Call SiliconFlow's hosted ``POST {endpoint}/rerank``.

    Wire format, observed against the live API on 2026-08-02::

        ->  {"model": "BAAI/bge-reranker-v2-m3", "query": "...",
             "documents": ["a", "b", "c"], "return_documents": false}
        <-  {"id": "...", "meta": {"tokens": {...}},
             "results": [{"index": 1, "document": null, "relevance_score": 0.64},
                         {"index": 0, ...}, {"index": 2, ...}]}

    **``results`` arrives in relevance order, not input order.** The observed
    response for three documents was index ``[1, 0, 2]``. This class implements
    the :class:`RerankerClient` contract — one score per passage, *in input
    order* — so the remapping is the whole job, not a detail. Zipping the
    response against the input would score every passage with another
    passage's relevance and silently invert the ranking.

    A note for whoever configures this: SiliconFlow runs two independent
    platforms. ``api.siliconflow.cn`` serves ``BAAI/bge-reranker-v2-m3``;
    ``api.siliconflow.com`` at the time of writing served only Qwen rerankers,
    and keys are not interchangeable between them — a ``.com`` key on ``.cn``
    returns 401, and the reverse returns "Token is invalid". The model this
    project needs is the one the evaluation used, so the endpoint is the ``.cn``
    one.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = f"{endpoint.rstrip('/')}/rerank"
        self._api_key = api_key
        self._model = model
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self._max_retries = max(1, max_retries)
        self._transport = transport

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []

        payload = await self._post_with_retries(query, passages)
        return self._scores_in_input_order(payload, len(passages))

    def _scores_in_input_order(self, payload: dict[str, object], expected: int) -> list[float]:
        results = payload.get("results")
        if not isinstance(results, list):
            raise RuntimeError("reranker API returned no 'results' list")
        if len(results) != expected:
            raise RuntimeError(
                f"reranker API returned {len(results)} scores for {expected} passages"
            )

        slots: list[float | None] = [None] * expected
        for item in results:
            if not isinstance(item, dict):
                raise RuntimeError("reranker API returned a non-object result item")
            index = item.get("index")
            if not isinstance(index, int) or isinstance(index, bool):
                raise RuntimeError("reranker API returned a result without an integer index")
            if not 0 <= index < expected:
                raise RuntimeError(f"reranker API returned out-of-range index {index}")
            if slots[index] is not None:
                raise RuntimeError(f"reranker API returned duplicate index {index}")
            slots[index] = _validate_score(item.get("relevance_score"))

        ordered: list[float] = []
        for position, score in enumerate(slots):
            if score is None:
                raise RuntimeError(f"reranker API returned no score for passage {position}")
            ordered.append(score)
        return ordered

    async def _post_with_retries(self, query: str, passages: list[str]) -> dict[str, object]:
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport
        ) as client:
            for attempt in range(self._max_retries):
                try:
                    response = await client.post(
                        self._url,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self._model,
                            "query": query,
                            "documents": passages,
                            "return_documents": False,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise RuntimeError("reranker API returned invalid JSON payload")
                    return payload
                except (
                    httpx.RemoteProtocolError,
                    httpx.ConnectError,
                    httpx.HTTPStatusError,
                ) as exc:
                    if (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code not in _RETRYABLE_STATUS
                    ):
                        raise
                    last_error = exc
                    if attempt >= self._max_retries - 1:
                        break
                    delay = min(30.0, 2.0 * (2**attempt))
                    logger.warning(
                        "reranker API request failed (attempt %s/%s), retrying in %.0fs: %s",
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
    provider: str = PROVIDER_SIDECAR,
    api_key: str = "",
) -> RerankerClient | None:
    """Build the reranker client for the current environment.

    Returns ``None`` when ``model`` is ``stub`` so callers keep identity rerank.
    ``provider`` defaults to the sidecar, so an environment that predates
    ``RERANKER_PROVIDER`` keeps exactly its current behaviour.
    """
    if model == "stub":
        return None

    normalized_endpoint = endpoint.strip()
    if not normalized_endpoint:
        raise ValueError("RERANKER_ENDPOINT is required when RERANKER_MODEL is not 'stub'")

    normalized_provider = provider.strip().lower() or PROVIDER_SIDECAR

    if normalized_provider == PROVIDER_SIDECAR:
        logger.info("using HTTP reranker client model=%s endpoint=%s", model, normalized_endpoint)
        return HttpRerankerClient(normalized_endpoint, max_retries=max_retries)

    if normalized_provider == PROVIDER_SILICONFLOW:
        if not api_key.strip():
            raise ValueError(
                f"RERANKER_API_KEY is required when RERANKER_PROVIDER is "
                f"'{PROVIDER_SILICONFLOW}'"
            )
        logger.info(
            "using SiliconFlow reranker client model=%s endpoint=%s",
            model,
            normalized_endpoint,
        )
        return SiliconFlowRerankerClient(
            normalized_endpoint,
            api_key=api_key.strip(),
            model=model,
            max_retries=max_retries,
        )

    raise ValueError(
        f"unknown RERANKER_PROVIDER {provider!r}; "
        f"expected one of {PROVIDER_SIDECAR!r}, {PROVIDER_SILICONFLOW!r}"
    )


def _validate_score(score: object) -> float:
    if not isinstance(score, int | float):
        raise ValueError("reranker score must be numeric")
    return float(score)
