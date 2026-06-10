"""Tool registry + agent SSE smoke tests."""

import uuid

from fastapi.testclient import TestClient

from dcode_agent.main import app
from dcode_agent.tools import default_registry

EXPECTED_TOOLS = {
    "search_code",
    "read_file",
    "find_definition",
    "find_references",
    "get_dependencies",
    "get_file_outline",
    "grep",
    "list_directory",
}


def test_registry_has_eight_canonical_tools() -> None:
    """DESIGN.md §2.3.2 enumerates exactly these eight tools."""
    registry = default_registry()
    assert set(registry.names()) == EXPECTED_TOOLS


def test_every_tool_exposes_args_schema_and_description() -> None:
    registry = default_registry()
    for name in registry.names():
        tool = registry.get(name)
        assert tool is not None
        assert tool.description, f"{name} missing description"
        schema = tool.ArgsSchema.model_json_schema()
        assert "properties" in schema


def test_cache_key_is_deterministic_and_namespaced() -> None:
    """Tool cache keys must follow DESIGN.md §3.3 `tool:{name}:{repo}:{hash}`."""
    tool = default_registry().get("search_code")
    assert tool is not None
    args = tool.ArgsSchema(query="x", k=5)
    key_a = tool.cache_key("repo-1", args)
    key_b = tool.cache_key("repo-1", args)
    assert key_a == key_b
    assert key_a.startswith("tool:search_code:repo-1:")


def test_healthz_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200


def test_tools_manifest_endpoint_lists_eight_tools() -> None:
    client = TestClient(app)
    response = client.get("/internal/tools")
    assert response.status_code == 200
    manifest = response.json()
    assert {entry["name"] for entry in manifest} == EXPECTED_TOOLS


def test_internal_query_streams_a_thought_and_final_answer() -> None:
    """Skeleton must emit at least one thought + one final_answer SSE event."""
    client = TestClient(app)
    rid = str(uuid.uuid4())
    with client.stream(
        "POST",
        "/internal/query",
        json={"repo_id": rid, "query": "How does X work?"},
    ) as response:
        assert response.status_code == 200
        body = b"".join(response.iter_bytes())
    assert b"event: thought" in body
    assert b"event: final_answer" in body
