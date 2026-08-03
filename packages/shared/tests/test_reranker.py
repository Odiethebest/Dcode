"""Tests for shared reranker clients.

The hosted-provider tests drive a mocked transport. They never call a live API:
CI holds no keys and must keep holding none (Deploy.md §5.3).
"""

import asyncio
import json

import httpx
import pytest
from dcode_shared.reranker import (
    HttpRerankerClient,
    SiliconFlowRerankerClient,
    create_reranker_client,
)
from pytest import raises


def test_create_reranker_client_returns_none_for_stub() -> None:
    assert create_reranker_client(model="stub") is None


def test_create_reranker_client_requires_endpoint_for_real_model() -> None:
    with raises(ValueError, match="RERANKER_ENDPOINT"):
        create_reranker_client(
            model="BAAI/bge-reranker-v2-m3",
            endpoint="",
        )


def test_create_reranker_client_builds_http_client() -> None:
    client = create_reranker_client(
        model="BAAI/bge-reranker-v2-m3",
        endpoint="http://localhost:8003",
    )
    assert isinstance(client, HttpRerankerClient)


# --- hosted provider: SiliconFlow ---------------------------------------


def _siliconflow_client(handler: object, *, max_retries: int = 3) -> SiliconFlowRerankerClient:
    return SiliconFlowRerankerClient(
        "https://api.siliconflow.cn/v1",
        api_key="test-key",
        model="BAAI/bge-reranker-v2-m3",
        max_retries=max_retries,
        timeout_seconds=1.0,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


async def test_siliconflow_client_returns_scores_in_input_order() -> None:
    """The API answers in relevance order; the contract here is input order.

    This is the single thing this client exists to get right. A live probe of
    three documents came back as index [1, 0, 2], so the mock reproduces that.
    Zipping the response against the input would give every passage another
    passage's score and invert the ranking, with nothing to notice it by.
    """
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("Authorization")
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "id": "probe",
                "meta": {"tokens": {"input_tokens": 289}},
                "results": [
                    {"index": 1, "document": None, "relevance_score": 0.64},
                    {"index": 0, "document": None, "relevance_score": 0.04},
                    {"index": 2, "document": None, "relevance_score": 0.0008},
                ],
            },
        )

    scores = await _siliconflow_client(handler).rerank("q", ["a", "b", "c"])

    assert scores == [0.04, 0.64, 0.0008]
    assert captured["url"] == "https://api.siliconflow.cn/v1/rerank"
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"] == {
        "model": "BAAI/bge-reranker-v2-m3",
        "query": "q",
        "documents": ["a", "b", "c"],
        "return_documents": False,
    }


async def test_siliconflow_client_returns_empty_without_calling_out() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made for an empty passage list")

    assert await _siliconflow_client(handler).rerank("q", []) == []


async def test_siliconflow_client_rejects_a_short_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 1.0}]})

    with raises(RuntimeError, match="1 scores for 2 passages"):
        await _siliconflow_client(handler).rerank("q", ["a", "b"])


async def test_siliconflow_client_rejects_an_out_of_range_index() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"index": 7, "relevance_score": 1.0}]})

    with raises(RuntimeError, match="out-of-range index 7"):
        await _siliconflow_client(handler).rerank("q", ["a"])


async def test_siliconflow_client_does_not_retry_an_unauthorized_key() -> None:
    """A .com key against .cn returns 401. Retrying it three times helps nobody."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, text='"Api key is invalid"')

    with raises(httpx.HTTPStatusError):
        await _siliconflow_client(handler).rerank("q", ["a"])
    assert attempts == 1


async def test_siliconflow_client_retries_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def no_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"detail": "slow down"})
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.5}]})

    assert await _siliconflow_client(handler).rerank("q", ["a"]) == [0.5]
    assert attempts == 2
    assert slept == [2.0]


def test_create_reranker_client_builds_the_siliconflow_client() -> None:
    client = create_reranker_client(
        model="BAAI/bge-reranker-v2-m3",
        endpoint="https://api.siliconflow.cn/v1",
        provider="siliconflow",
        api_key="test-key",
    )
    assert isinstance(client, SiliconFlowRerankerClient)


def test_create_reranker_client_requires_a_key_for_the_hosted_provider() -> None:
    with raises(ValueError, match="RERANKER_API_KEY"):
        create_reranker_client(
            model="BAAI/bge-reranker-v2-m3",
            endpoint="https://api.siliconflow.cn/v1",
            provider="siliconflow",
            api_key="",
        )


def test_create_reranker_client_rejects_an_unknown_provider() -> None:
    with raises(ValueError, match="unknown RERANKER_PROVIDER"):
        create_reranker_client(
            model="BAAI/bge-reranker-v2-m3",
            endpoint="https://example.invalid/v1",
            provider="not-a-provider",
        )


def test_stub_short_circuits_before_the_provider_is_consulted() -> None:
    assert create_reranker_client(model="stub", provider="siliconflow") is None
