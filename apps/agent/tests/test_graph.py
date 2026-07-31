"""LangGraph node tests for the agent's first-pass orchestration."""

import logging
from typing import Any, ClassVar
from uuid import uuid4

from dcode_agent.graph import (
    build_graph,
    contextualize_node,
    groundedness_node,
    plan_node,
    synthesize_node,
    tool_call_node,
)
from dcode_agent.state import AgentState
from dcode_agent.tools.base import Tool, ToolRegistry
from dcode_shared.db.models import Chunk, Symbol
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


class DummyReadFileArgs(BaseModel):
    path: str
    line_range: tuple[int, int]


class DummyReadFileResult(BaseModel):
    path: str
    line_range: tuple[int, int]
    content: str


class DummyReadFileTool(Tool[DummyReadFileArgs, DummyReadFileResult]):
    name: ClassVar[str] = "read_file"
    description: ClassVar[str] = "Dummy read_file tool for graph tests."
    ArgsSchema: ClassVar[type[BaseModel]] = DummyReadFileArgs

    async def execute(self, repo_id: str, args: DummyReadFileArgs) -> DummyReadFileResult:
        return DummyReadFileResult(
            path=args.path,
            line_range=args.line_range,
            content="class HTTPBasicAuth(AuthBase): ...",
        )


class DummyReferencesTool(Tool[DummyArgs, DummyResult]):
    name: ClassVar[str] = "find_references"
    description: ClassVar[str] = "Dummy find_references tool for graph tests."
    ArgsSchema: ClassVar[type[BaseModel]] = DummyArgs

    async def execute(self, repo_id: str, args: DummyArgs) -> DummyResult:
        return DummyResult(
            locations=[
                {
                    "symbol": "requests.models.PreparedRequest.prepare_auth",
                    "file_path": "src/requests/models.py",
                    "line": 589,
                    "chunk_id": None,
                }
            ]
        )


class DummyOutlineArgs(BaseModel):
    path: str


class DummyOutlineResult(BaseModel):
    path: str
    locations: list[dict[str, Any]]


class DummyOutlineTool(Tool[DummyOutlineArgs, DummyOutlineResult]):
    name: ClassVar[str] = "get_file_outline"
    description: ClassVar[str] = "Dummy get_file_outline tool for graph tests."
    ArgsSchema: ClassVar[type[BaseModel]] = DummyOutlineArgs

    async def execute(self, repo_id: str, args: DummyOutlineArgs) -> DummyOutlineResult:
        return DummyOutlineResult(
            path=args.path,
            locations=[
                {
                    "symbol": "requests.auth.HTTPBasicAuth",
                    "file_path": args.path,
                    "line": 85,
                    "chunk_id": None,
                }
            ],
        )


class FakeEmitter:
    def __init__(self) -> None:
        self.thoughts: list[tuple[int, str]] = []
        self.tool_calls: list[tuple[int, str, dict[str, Any]]] = []
        self.tool_results: list[tuple[int, str, str]] = []
        self.partials: list[str] = []

    async def emit_thought(self, step: int, content: str) -> None:
        self.thoughts.append((step, content))

    async def emit_tool_call(self, step: int, tool: str, args: dict[str, Any]) -> None:
        self.tool_calls.append((step, tool, args))

    async def emit_tool_result(self, step: int, tool: str, result_summary: str) -> None:
        self.tool_results.append((step, tool, result_summary))

    async def emit_partial_answer(self, delta: str) -> None:
        self.partials.append(delta)


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


async def test_plan_node_extracts_symbols_from_reference_queries() -> None:
    queries = [
        "Who calls send in requests?",
        "who references send",
        "find callers of send",
        "Who calls `send`?",
    ]

    for query in queries:
        state = AgentState(repo_id=str(uuid4()), query=query)

        updated = await plan_node(state)

        assert updated.pending_tool_name == "find_references"
        assert updated.pending_tool_args == {"symbol": "send"}


async def test_plan_node_defaults_to_search_code() -> None:
    state = AgentState(repo_id=str(uuid4()), query="auth related code")

    updated = await plan_node(state)

    assert updated.pending_tool_name == "search_code"
    assert updated.pending_tool_args == {"query": "auth related code", "k": 5}


async def test_plan_node_routes_dependents_queries() -> None:
    queries = [
        "Who imports `requests.sessions`?",
        "importers of requests.auth",
        "reverse dependencies of requests.models",
        "What are the dependents of requests.api?",
    ]
    for query in queries:
        state = AgentState(repo_id=str(uuid4()), query=query)
        updated = await plan_node(state)
        assert updated.pending_tool_name == "get_dependents", query


async def test_tool_call_node_executes_and_then_hits_cache(caplog) -> None:
    caplog.set_level(logging.INFO, logger="dcode.agent.graph")
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
    assert any('"event": "tool_call"' in record.message for record in caplog.records)
    assert any('"event": "tool_result"' in record.message for record in caplog.records)


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
    # Guardrail: with no db the single citation is unverified, so the file:line
    # reference is redacted from the answer and a warning footer is appended.
    assert "src/requests/auth.py:85" not in result["final_answer"]
    assert "[unverified reference removed]" in result["final_answer"]
    assert len(result["tool_calls"]) == 1
    assert emitter.thoughts
    assert emitter.tool_calls
    assert emitter.tool_results


class FakeScalars:
    """The slice of SQLAlchemy's Result that `_verify_symbol` uses."""

    def __init__(self, rows: list[Symbol]) -> None:
        self._rows = rows

    def scalars(self) -> "FakeScalars":
        return self

    def all(self) -> list[Symbol]:
        return list(self._rows)


class FakeGroundednessSession:
    """Minimal async session that answers groundedness verification queries."""

    def __init__(self, *, chunks: list[Chunk], symbols: list[Symbol]) -> None:
        self.chunks = chunks
        self.symbols = symbols

    async def execute(self, stmt: object) -> FakeScalars:
        """Superset for the repo; the name filter is deliberately not emulated.

        See the same method in `test_groundedness.py` — reimplementing the SQL
        narrowing in a fake would be a third copy of the matching rule.
        """
        params = stmt.compile().params  # type: ignore[attr-defined]
        return FakeScalars([s for s in self.symbols if s.repo_id == params["repo_id_1"]])

    async def scalar(self, stmt: object) -> Chunk | Symbol | None:
        compiled = stmt.compile()
        sql = str(stmt)
        params = compiled.params
        if "FROM chunks" in sql:
            repo_id = params["repo_id_1"]
            file_path = params["file_path_1"]
            line = params["start_line_1"]
            for chunk in self.chunks:
                if (
                    chunk.repo_id == repo_id
                    and chunk.file_path == file_path
                    and chunk.start_line <= line <= chunk.end_line
                ):
                    return chunk
            return None
        if "FROM symbols" in sql:
            repo_id = params["repo_id_1"]
            qualified_name = params["qualified_name_1"]
            for symbol in self.symbols:
                if symbol.repo_id == repo_id and symbol.qualified_name == qualified_name:
                    return symbol
            return None
        raise AssertionError(f"unexpected statement: {sql}")


def _grounded_session(repo_id: Any) -> FakeGroundednessSession:
    """A session that verifies every reference the multi-hop trace cites."""
    return FakeGroundednessSession(
        chunks=[
            Chunk(
                id=uuid4(),
                repo_id=repo_id,
                file_path="src/requests/auth.py",
                chunk_type="class",
                parent_symbol=None,
                symbol_name="HTTPBasicAuth",
                signature=None,
                start_line=85,
                end_line=113,
                imports=[],
                content="class HTTPBasicAuth(AuthBase): ...",
                embedding=[0.0],
            ),
            Chunk(
                id=uuid4(),
                repo_id=repo_id,
                file_path="src/requests/models.py",
                chunk_type="method",
                parent_symbol="PreparedRequest",
                symbol_name="prepare_auth",
                signature=None,
                start_line=580,
                end_line=600,
                imports=[],
                content="def prepare_auth(self, auth, url): ...",
                embedding=[0.0],
            ),
        ],
        symbols=[
            Symbol(
                id=uuid4(),
                repo_id=repo_id,
                qualified_name="requests.auth.HTTPBasicAuth",
                kind="class",
                file_path="src/requests/auth.py",
                line=85,
                chunk_id=None,
            ),
            Symbol(
                id=uuid4(),
                repo_id=repo_id,
                qualified_name="requests.models.PreparedRequest.prepare_auth",
                kind="method",
                file_path="src/requests/models.py",
                line=589,
                chunk_id=None,
            ),
        ],
    )


async def test_groundedness_node_resolves_evidence_ids_without_treating_code_as_citations() -> None:
    repo_uuid = uuid4()
    state = AgentState(
        repo_id=str(repo_uuid),
        query="它调用了哪些函数？",
        draft_answer="源码中出现 `self.client.retrieve`，证据见 [C1]。",
        evidence_catalog={"C1": "src/requests/auth.py:85"},
        runtime={"db": _grounded_session(repo_uuid)},
    )

    updated = await groundedness_node(state)

    assert updated.groundedness_score == 1.0
    assert "`self.client.retrieve`" in (updated.final_answer or "")
    assert "`src/requests/auth.py:85`" in (updated.final_answer or "")
    assert "[C1]" not in (updated.final_answer or "")


async def test_build_graph_runs_multihop_for_architecture_query() -> None:
    repo_uuid = uuid4()
    repo_id = str(repo_uuid)
    emitter = FakeEmitter()
    registry = _registry(
        DummySearchTool(),
        DummyReadFileTool(),
        DummyReferencesTool(),
        DummyOutlineTool(),
    )
    # A db that verifies every reference the trace cites, so the groundedness
    # guardrail keeps them all (the fully-grounded end-to-end path).
    db = _grounded_session(repo_uuid)
    compiled = build_graph()

    result = await compiled.ainvoke(
        AgentState(
            repo_id=repo_id,
            query="How is authentication wired end-to-end?",
            runtime={
                "tool_registry": registry,
                "tool_cache": {},
                "emitter": emitter,
                "db": db,
            },
        )
    )

    assert [call["tool"] for call in result["tool_calls"]] == [
        "search_code",
        "read_file",
        "find_references",
        "get_file_outline",
    ]
    assert "Agent trace" in result["final_answer"]
    assert "src/requests/auth.py:85" in result["final_answer"]
    assert "src/requests/models.py:589" in result["final_answer"]
    # Every cited reference verified → nothing redacted, groundedness 1.0.
    assert result["groundedness_score"] == 1.0
    assert "[unverified reference removed]" not in result["final_answer"]
    assert len(emitter.thoughts) == 4
    assert len(emitter.tool_calls) == 4
    assert len(emitter.tool_results) == 4


class DummyFailingSearchTool(Tool[DummySearchArgs, DummySearchResult]):
    name: ClassVar[str] = "search_code"
    description: ClassVar[str] = "Dummy search tool that always fails."
    ArgsSchema: ClassVar[type[BaseModel]] = DummySearchArgs

    async def execute(self, repo_id: str, args: DummySearchArgs) -> DummySearchResult:
        raise RuntimeError("retrieval API unavailable")


async def test_tool_failure_degrades_to_synthesis_without_raising() -> None:
    repo_id = str(uuid4())
    emitter = FakeEmitter()
    registry = _registry(DummyFailingSearchTool())
    compiled = build_graph()

    result = await compiled.ainvoke(
        AgentState(
            repo_id=repo_id,
            query="auth related code",
            runtime={"tool_registry": registry, "tool_cache": {}, "emitter": emitter},
        )
    )

    # A tool failure is recorded and degrades to a synthesized answer, not an abort.
    assert result["error"] is not None
    assert "retrieval API unavailable" in result["error"]
    assert result["final_answer"] is not None
    assert "⚠️" in result["final_answer"]
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0].get("error")  # failure recorded on the tool call
    assert emitter.tool_calls  # tool_call emitted before execution
    assert "error:" in emitter.tool_results[-1][2]  # failure surfaced as a tool_result


class _RewriteLLM:
    """Duck-typed LLM that only implements contextualize (query rewrite)."""

    def __init__(self, rewritten: str) -> None:
        self.rewritten = rewritten
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    async def contextualize(self, *, question: str, history: list[dict[str, str]]) -> str | None:
        self.calls.append((question, history))
        return self.rewritten


async def test_contextualize_node_rewrites_followup_with_history() -> None:
    emitter = FakeEmitter()
    llm = _RewriteLLM("Who calls HTTPBasicAuth?")
    state = AgentState(
        repo_id=str(uuid4()),
        query="who calls it?",
        history=[{"role": "user", "content": "explain HTTPBasicAuth"}],
        runtime={"llm": llm, "emitter": emitter},
    )

    updated = await contextualize_node(state)

    assert updated.query == "Who calls HTTPBasicAuth?"  # rewritten drives retrieval
    assert updated.raw_query == "who calls it?"  # original preserved for display
    assert llm.calls[0][0] == "who calls it?"
    assert emitter.thoughts  # the rewrite is surfaced in the trace


async def test_contextualize_node_is_noop_without_history() -> None:
    llm = _RewriteLLM("should not be used")
    state = AgentState(repo_id=str(uuid4()), query="where is X?", runtime={"llm": llm})

    updated = await contextualize_node(state)

    assert updated.query == "where is X?"
    assert updated.raw_query is None
    assert llm.calls == []  # a single-turn request never calls the LLM


async def test_contextualize_node_is_noop_without_llm() -> None:
    state = AgentState(
        repo_id=str(uuid4()),
        query="who calls it?",
        history=[{"role": "user", "content": "explain X"}],
        runtime={},  # no LLM (stub synthesis) → the raw query flows through
    )

    updated = await contextualize_node(state)

    assert updated.query == "who calls it?"
    assert updated.raw_query is None
