"""Query route tests: SSE proxying and query-cache behavior."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import httpx
import pytest
from dcode_api.deps import get_agent_client, get_redis
from dcode_api.main import app
from dcode_shared.cache import query_cache_key
from fastapi.testclient import TestClient


class FakeStreamResponse:
    def __init__(self, status_code: int, chunks: list[bytes]) -> None:
        self.status_code = status_code
        self._chunks = chunks

    async def __aenter__(self) -> "FakeStreamResponse":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


class FakeAgentClient:
    def __init__(self, response: FakeStreamResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def stream(self, method: str, url: str, json: dict[str, object]) -> FakeStreamResponse:
        self.calls.append((method, url, json))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.setex_calls: list[tuple[str, int, str]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.setex_calls.append((key, ttl, value))


def override_dependencies(agent: FakeAgentClient, redis: FakeRedis) -> None:
    async def override_agent() -> FakeAgentClient:
        return agent

    async def override_redis() -> FakeRedis:
        return redis

    app.dependency_overrides[get_agent_client] = override_agent
    app.dependency_overrides[get_redis] = override_redis


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_query_route_proxies_and_caches_successful_sse_stream() -> None:
    repo_id = str(uuid4())
    body = {"repo_id": repo_id, "query": "Where is `HTTPBasicAuth` defined?"}
    payload = (
        b"event: thought\n"
        b'data: {"step":1,"content":"route"}\n\n'
        b"event: final_answer\n"
        b'data: {"answer":"ok","citations":[],"groundedness":1.0}\n\n'
    )
    agent = FakeAgentClient(FakeStreamResponse(200, [payload[:45], payload[45:]]))
    redis = FakeRedis()
    override_dependencies(agent, redis)

    response = TestClient(app).post("/api/v1/query", json=body)

    assert response.status_code == 200
    assert response.content == payload
    assert agent.calls == [("POST", "/internal/query", body)]
    key = query_cache_key(repo_id, body["query"])
    assert redis.setex_calls
    assert redis.setex_calls[0][0] == key
    assert redis.values[key] == payload.decode("utf-8")


def test_query_route_replays_cached_sse_without_hitting_agent() -> None:
    repo_id = str(uuid4())
    query = "Where is `HTTPBasicAuth` defined?"
    key = query_cache_key(repo_id, query)
    cached = (
        "event: final_answer\n"
        'data: {"answer":"cached","citations":[],"groundedness":1.0}\n\n'
    )
    agent = FakeAgentClient(FakeStreamResponse(200, [b"unused"]))
    redis = FakeRedis({key: cached})
    override_dependencies(agent, redis)

    response = TestClient(app).post("/api/v1/query", json={"repo_id": repo_id, "query": query})

    assert response.status_code == 200
    assert response.text == cached
    assert agent.calls == []


def test_query_route_does_not_cache_error_streams() -> None:
    repo_id = str(uuid4())
    body = {"repo_id": repo_id, "query": "bad"}
    payload = (
        b"event: thought\n"
        b'data: {"step":1,"content":"route"}\n\n'
        b"event: error\n"
        b'data: {"code":"INTERNAL","message":"boom"}\n\n'
    )
    agent = FakeAgentClient(FakeStreamResponse(200, [payload]))
    redis = FakeRedis()
    override_dependencies(agent, redis)

    response = TestClient(app).post("/api/v1/query", json=body)

    assert response.status_code == 200
    assert response.content == payload
    assert redis.setex_calls == []


def test_query_route_emits_stub_when_agent_is_unreachable() -> None:
    repo_id = str(uuid4())
    request = httpx.Request("POST", "http://agent/internal/query")
    exc = httpx.ConnectError("connection refused", request=request)
    agent = FakeAgentClient(exc)
    redis = FakeRedis()
    override_dependencies(agent, redis)

    response = TestClient(app).post("/api/v1/query", json={"repo_id": repo_id, "query": "x"})

    assert response.status_code == 200
    assert "event: thought" in response.text
    assert "event: error" in response.text
    assert redis.setex_calls == []
