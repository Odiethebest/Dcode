"""SSE query-stream tests for the agent entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from dcode_agent.main import app
from dcode_agent.settings import agent_settings
from dcode_shared.internal import internal_auth_headers
from fastapi.testclient import TestClient


class FakeCompiledGraph:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def ainvoke(self, state: Any) -> dict[str, Any]:
        emitter = state.runtime["emitter"]
        await emitter.emit_thought(step=1, content="route to definition lookup")
        await emitter.emit_tool_call(
            step=1,
            tool="find_definition",
            args={"symbol": "HTTPBasicAuth"},
        )
        await emitter.emit_tool_result(
            step=1,
            tool="find_definition",
            result_summary="1 locations; top src/requests/auth.py:85",
        )
        if self.fail:
            raise RuntimeError("boom")
        return {
            "final_answer": "Definition matches:\n- `src.requests.auth.HTTPBasicAuth` at `src/requests/auth.py:85`",
            "citations": [
                {
                    "symbol": "src.requests.auth.HTTPBasicAuth",
                    "file_path": "src/requests/auth.py",
                    "line": 85,
                    "verified": True,
                }
            ],
            "groundedness_score": 1.0,
        }


@asynccontextmanager
async def fake_db_session_factory() -> AsyncIterator[object]:
    yield object()


def test_internal_query_streams_graph_events() -> None:
    with TestClient(app) as client:
        app.state.compiled_graph = FakeCompiledGraph()
        app.state.db_session_factory = fake_db_session_factory
        app.state.tool_cache = {}
        with client.stream(
            "POST",
            "/internal/query",
            json={"repo_id": str(uuid4()), "query": "Where is `HTTPBasicAuth` defined?"},
            headers=internal_auth_headers(agent_settings.internal_api_key),
        ) as response:
            assert response.status_code == 200
            body = b"".join(response.iter_bytes())

    assert b"event: thought" in body
    assert b"event: tool_call" in body
    assert b"event: tool_result" in body
    assert b"event: citation" in body
    assert b"event: partial_answer" in body
    assert b"event: final_answer" in body
    assert b"src.requests.auth.HTTPBasicAuth" in body
    assert b"src/requests/auth.py" in body


def test_internal_query_streams_error_when_graph_fails() -> None:
    with TestClient(app) as client:
        app.state.compiled_graph = FakeCompiledGraph(fail=True)
        app.state.db_session_factory = fake_db_session_factory
        app.state.tool_cache = {}
        with client.stream(
            "POST",
            "/internal/query",
            json={"repo_id": str(uuid4()), "query": "Where is `HTTPBasicAuth` defined?"},
            headers=internal_auth_headers(agent_settings.internal_api_key),
        ) as response:
            assert response.status_code == 200
            body = b"".join(response.iter_bytes())

    assert b"event: thought" in body
    assert b"event: tool_call" in body
    assert b"event: tool_result" in body
    assert b"event: error" in body
    assert b"boom" in body


def test_internal_query_requires_service_auth() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/internal/query",
            json={"repo_id": str(uuid4()), "query": "Where is `HTTPBasicAuth` defined?"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"
