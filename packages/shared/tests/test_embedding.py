"""Tests for shared embedding clients."""

from dcode_shared.embedding import (
    HttpEmbeddingClient,
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
