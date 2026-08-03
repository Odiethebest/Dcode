"""Tests for shared embedding clients.

The hosted-provider tests drive a mocked transport. They never call a live API:
CI holds no keys and must keep holding none (Deploy.md §5.3).
"""

import asyncio
import json

import httpx
import pytest
from dcode_shared.embedding import (
    HttpEmbeddingClient,
    JinaApiEmbeddingClient,
    StubEmbeddingClient,
    create_embedding_client,
)
from pytest import raises


async def test_stub_embedding_client_returns_zero_vectors() -> None:
    client = StubEmbeddingClient(dim=3)
    vectors = await client.embed_batch(["a", "b"])
    assert vectors == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]


def test_create_embedding_client_uses_stub_when_model_is_stub() -> None:
    client = create_embedding_client(model="stub", dim=4)
    assert isinstance(client, StubEmbeddingClient)


def test_create_embedding_client_requires_endpoint_for_real_model() -> None:
    with raises(ValueError, match="EMBEDDING_ENDPOINT"):
        create_embedding_client(
            model="jinaai/jina-embeddings-v2-base-code",
            dim=768,
            endpoint="",
        )


def test_create_embedding_client_builds_http_client() -> None:
    client = create_embedding_client(
        model="jinaai/jina-embeddings-v2-base-code",
        dim=768,
        endpoint="http://localhost:8002",
    )
    assert isinstance(client, HttpEmbeddingClient)


# --- hosted provider: Jina AI -------------------------------------------


def _jina_client(
    handler: object,
    *,
    dim: int = 3,
    batch_size: int = 8,
    max_retries: int = 3,
) -> JinaApiEmbeddingClient:
    return JinaApiEmbeddingClient(
        "https://api.jina.ai/v1",
        api_key="test-key",
        model="jina-embeddings-v2-base-code",
        dim=dim,
        batch_size=batch_size,
        max_retries=max_retries,
        timeout_seconds=1.0,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


async def test_jina_client_places_vectors_by_index_not_arrival_order() -> None:
    """The response identifies vectors by index and may not arrive in order.

    Zipping arrival order against the inputs would attach the wrong embedding
    to a chunk — silent corruption with no error, only worse retrieval. So the
    mock deliberately answers out of order.
    """
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("Authorization")
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "model": "jina-embeddings-v2-base-code",
                "object": "list",
                "usage": {"total_tokens": 6, "prompt_tokens": 6},
                "data": [
                    {"object": "embedding", "index": 2, "embedding": [2.0, 2.0, 2.0]},
                    {"object": "embedding", "index": 0, "embedding": [0.0, 0.1, 0.2]},
                    {"object": "embedding", "index": 1, "embedding": [1.0, 1.0, 1.0]},
                ],
            },
        )

    vectors = await _jina_client(handler).embed_batch(["a", "b", "c"])

    assert vectors == [[0.0, 0.1, 0.2], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0]]
    assert captured["url"] == "https://api.jina.ai/v1/embeddings"
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"] == {
        "model": "jina-embeddings-v2-base-code",
        "input": ["a", "b", "c"],
    }


async def test_jina_client_batches_and_preserves_order_across_batches() -> None:
    seen: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        batch = json.loads(request.content)["input"]
        seen.append(batch)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": position, "embedding": [float(ord(text))] * 3}
                    for position, text in reversed(list(enumerate(batch)))
                ]
            },
        )

    vectors = await _jina_client(handler, batch_size=2).embed_batch(["a", "b", "c"])

    assert seen == [["a", "b"], ["c"]]
    assert vectors == [[97.0] * 3, [98.0] * 3, [99.0] * 3]


async def test_jina_client_rejects_a_dimension_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

    with raises(ValueError, match="embedding dimension mismatch"):
        await _jina_client(handler, dim=3).embed_batch(["a"])


async def test_jina_client_rejects_a_short_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 2.0, 3.0]}]})

    with raises(RuntimeError, match="1 vectors for 2 inputs"):
        await _jina_client(handler).embed_batch(["a", "b"])


async def test_jina_client_rejects_a_duplicated_index() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [1.0, 1.0, 1.0]},
                    {"index": 0, "embedding": [2.0, 2.0, 2.0]},
                ]
            },
        )

    with raises(RuntimeError, match="duplicate index 0"):
        await _jina_client(handler).embed_batch(["a", "b"])


async def test_jina_client_does_not_retry_an_unauthorized_key() -> None:
    """401 does not improve by asking again, and a wrong key should say so now."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"detail": "unauthorized"})

    with raises(httpx.HTTPStatusError):
        await _jina_client(handler).embed_batch(["a"])
    assert attempts == 1


async def test_jina_client_retries_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 is the normal free-tier response under load, so it must be retried.

    The sidecar client retries only 5xx, which is right for a service we run
    and wrong for a metered one. The backoff sleep is captured rather than
    waited out — the claim under test is that it retried and backed off, not
    how long a test run takes.
    """
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
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 1.0, 1.0]}]})

    vectors = await _jina_client(handler).embed_batch(["a"])

    assert attempts == 2
    assert slept == [2.0]
    assert vectors == [[1.0, 1.0, 1.0]]


def test_create_embedding_client_builds_the_jina_api_client() -> None:
    client = create_embedding_client(
        model="jina-embeddings-v2-base-code",
        dim=768,
        endpoint="https://api.jina.ai/v1",
        provider="jina_api",
        api_key="test-key",
    )
    assert isinstance(client, JinaApiEmbeddingClient)


def test_create_embedding_client_requires_a_key_for_the_hosted_provider() -> None:
    with raises(ValueError, match="EMBEDDING_API_KEY"):
        create_embedding_client(
            model="jina-embeddings-v2-base-code",
            dim=768,
            endpoint="https://api.jina.ai/v1",
            provider="jina_api",
            api_key="   ",
        )


def test_create_embedding_client_rejects_an_unknown_provider() -> None:
    with raises(ValueError, match="unknown EMBEDDING_PROVIDER"):
        create_embedding_client(
            model="jina-embeddings-v2-base-code",
            dim=768,
            endpoint="https://example.invalid/v1",
            provider="not-a-provider",
        )


def test_stub_short_circuits_before_the_provider_is_consulted() -> None:
    """Stub mode must stay usable with no endpoint and no key, whatever the provider says."""
    client = create_embedding_client(model="stub", dim=4, provider="jina_api")
    assert isinstance(client, StubEmbeddingClient)
