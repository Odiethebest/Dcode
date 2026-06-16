"""Tool registry + agent manifest smoke tests."""

from dcode_agent.main import app
from dcode_agent.settings import agent_settings
from dcode_agent.tools import default_registry
from dcode_shared.internal import internal_auth_headers
from fastapi.testclient import TestClient

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
    # The manifest endpoint reads app.state.tool_registry which is set in
    # the lifespan handler — TestClient's context manager triggers it.
    with TestClient(app) as client:
        response = client.get(
            "/internal/tools",
            headers=internal_auth_headers(agent_settings.internal_api_key),
        )
    assert response.status_code == 200
    manifest = response.json()
    assert {entry["name"] for entry in manifest} == EXPECTED_TOOLS


def test_tools_manifest_requires_service_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/internal/tools")

    assert response.status_code == 403
