"""Tests for shared reranker clients."""

from dcode_shared.reranker import HttpRerankerClient, create_reranker_client
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
