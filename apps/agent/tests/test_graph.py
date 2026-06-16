"""LangGraph node tests for the agent's first-pass orchestration."""

from typing import Any, ClassVar
from uuid import uuid4

from dcode_agent.graph import build_graph, plan_node, synthesize_node, tool_call_node
from dcode_agent.state import AgentState
from dcode_agent.tools.base import Tool, ToolRegistry
from pydantic import BaseModel


class DummyArgs(BaseModel):
    symbol: str


class DummyResult(BaseModel):
    locations: list[dict[str, Any]]


class DummyTool(Tool[DummyArgs, DummyResult]):
    name: ClassVar[str] = "find_definition"
    description: ClassVar[str] = "Dummy tool for graph tests."
    ArgsSchema: ClassVar[type[BaseModel]] = DummyArgs

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, repo_id: str, args: DummyArgs) -> DummyResult:
        self.calls += 1
        return DummyResult(
            locations=[
                {
                    "symbol": args.symbol,
                    "file_path": "src/requests/auth.py",
                    "line": 85,
                    "chunk_id": None,
                }
            ]
        )


class DummySearchArgs(BaseModel):
    query: str
    k: int


class DummySearchResult(BaseModel):
    chunks: list[dict[str, Any]]


class DummySearchTool(Tool[DummySearchArgs, DummySearchResult]):
    name: ClassVar[str] = "search_code"
    description: ClassVar[str] = "Dummy search tool for graph tests."
    ArgsSchema: ClassVar[type[BaseModel]] = DummySearchArgs

    async def execute(self, repo_id: str, args: DummySearchArgs) -> DummySearchResult:
        return DummySearchResult(
            chunks=[
                {
                    "chunk_id": str(uuid4()),
                    "file_path": "src/requests/auth.py",
                    "symbol_name": "HTTPBasicAuth",
                    "start_line": 85,
                    "end_line": 113,
                    "content": "class HTTPBasicAuth(AuthBase): ...",
                    "score": 1.0,
                    "score_components": {"dense": 0.0, "sparse": 1.0, "rerank": 1.0},
                }
            ]
        )


class FakeEmitter:
    def __init__(self) -> None:
        self.thoughts: list[tuple[int, str]] = []
        self.tool_calls: list[tuple[int, str, dict[str, Any]]] = []
        self.tool_results: list[tuple[int, str, str]] = []

    async def emit_thought(self, step: int, content: str) -> None:
        self.thoughts.append((step, content))

    async def emit_tool_call(self, step: int, tool: str, args: dict[str, Any]) -> None:
        self.tool_calls.append((step, tool, args))

    async def emit_tool_result(self, step: int, tool: str, result_summary: str) -> None:
        self.tool_results.append((step, tool, result_summary))


def _registry(*tools: Tool[Any, Any]) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


async def test_plan_node_routes_definition_queries() -> None:
    state = AgentState(repo_id=str(uuid4()), query="Where is `HTTPBasicAuth` defined?")

    updated = await plan_node(state)

    assert updated.pending_tool_name == "find_definition"
    assert updated.pending_tool_args == {"symbol": "HTTPBasicAuth"}
    assert "find_definition" in updated.thoughts[0]


async def test_plan_node_defaults_to_search_code() -> None:
    state = AgentState(repo_id=str(uuid4()), query="auth related code")

    updated = await plan_node(state)

    assert updated.pending_tool_name == "search_code"
    assert updated.pending_tool_args == {"query": "auth related code", "k": 5}


async def test_tool_call_node_executes_and_then_hits_cache() -> None:
    tool = DummyTool()
    registry = _registry(tool)
    emitter = FakeEmitter()
    cache: dict[str, str] = {}
    repo_id = str(uuid4())
    state = AgentState(
        repo_id=repo_id,
        query="Where is `HTTPBasicAuth` defined?",
        pending_tool_name="find_definition",
        pending_tool_args={"symbol": "HTTPBasicAuth"},
        runtime={"tool_registry": registry, "tool_cache": cache, "emitter": emitter},
    )

    first = await tool_call_node(state)
    second = await tool_call_node(
        AgentState(
            repo_id=repo_id,
            query=state.query,
            pending_tool_name="find_definition",
            pending_tool_args={"symbol": "HTTPBasicAuth"},
            runtime={"tool_registry": registry, "tool_cache": cache, "emitter": emitter},
        )
    )

    assert tool.calls == 1
    assert first.step_count == 1
    assert first.observations[0]["cached"] is False
    assert second.observations[0]["cached"] is True
    assert emitter.tool_calls[0][1] == "find_definition"
    assert "src/requests/auth.py" in emitter.tool_results[0][2]


async def test_synthesize_node_formats_search_observation() -> None:
    state = AgentState(
        repo_id=str(uuid4()),
        query="auth related code",
        observations=[
            {
                "tool": "search_code",
                "args": {"query": "auth related code", "k": 5},
                "result": {
                    "chunks": [
                        {
                            "chunk_id": str(uuid4()),
                            "file_path": "src/requests/auth.py",
                            "symbol_name": "HTTPBasicAuth",
                            "start_line": 85,
                            "end_line": 113,
                            "content": "class HTTPBasicAuth(AuthBase): ...",
                            "score": 1.0,
                            "score_components": {"dense": 0.0, "sparse": 1.0, "rerank": 1.0},
                        }
                    ]
                },
                "cached": False,
            }
        ],
    )

    updated = await synthesize_node(state)

    assert "Top code hits" in updated.draft_answer
    assert "`src/requests/auth.py:85`" in updated.draft_answer
    assert updated.citations[0]["symbol"] == "HTTPBasicAuth"


async def test_build_graph_runs_one_tool_then_synthesizes() -> None:
    repo_id = str(uuid4())
    emitter = FakeEmitter()
    registry = _registry(DummyTool(), DummySearchTool())
    compiled = build_graph()

    result = await compiled.ainvoke(
        AgentState(
            repo_id=repo_id,
            query="Where is `HTTPBasicAuth` defined?",
            runtime={"tool_registry": registry, "tool_cache": {}, "emitter": emitter},
        )
    )

    assert result["final_answer"] is not None
    assert "Definition matches" in result["final_answer"]
    assert result["groundedness_score"] == 0.0
    assert len(result["tool_calls"]) == 1
    assert emitter.thoughts
    assert emitter.tool_calls
    assert emitter.tool_results
