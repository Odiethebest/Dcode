"""LLM synthesis node — streams deltas live, and degrades to the template."""

from collections.abc import AsyncIterator
from typing import Any

from dcode_agent.graph import synthesize_node
from dcode_agent.llm import ResponseLanguage
from dcode_agent.state import AgentState


class _FakeLLM:
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.calls: list[tuple[str, str, ResponseLanguage]] = []

    async def stream(
        self,
        *,
        question: str,
        context: str,
        response_language: ResponseLanguage,
    ) -> AsyncIterator[str]:
        self.calls.append((question, context, response_language))
        for chunk in self.chunks:
            yield chunk


class _BoomLLM:
    async def stream(
        self,
        *,
        question: str,
        context: str,
        response_language: ResponseLanguage,
    ) -> AsyncIterator[str]:
        raise RuntimeError("boom")
        yield ""  # unreachable; makes this an async generator


class _FakeEmitter:
    def __init__(self) -> None:
        self.partials: list[str] = []
        self.thoughts: list[str] = []

    async def emit_partial_answer(self, delta: str) -> None:
        self.partials.append(delta)

    async def emit_thought(self, step: int, content: str) -> None:
        self.thoughts.append(content)


def _search_state(runtime: dict[str, Any]) -> AgentState:
    state = AgentState(
        repo_id="11111111-1111-1111-1111-111111111111",
        query="how does auth work?",
        runtime=runtime,
    )
    state.observations.append(
        {
            "tool": "search_code",
            "args": {},
            "cached": False,
            "result": {
                "chunks": [
                    {
                        "symbol_name": "HTTPBasicAuth",
                        "file_path": "src/requests/auth.py",
                        "start_line": 85,
                        "end_line": 90,
                        "content": "class HTTPBasicAuth(AuthBase): ...",
                    }
                ]
            },
        }
    )
    return state


async def test_synthesis_streams_llm_deltas() -> None:
    emitter = _FakeEmitter()
    llm = _FakeLLM(["Auth is implemented here ", "[C1]", "."])
    state = await synthesize_node(_search_state({"llm": llm, "emitter": emitter}))
    assert state.draft_answer == "Auth is implemented here [C1]."
    assert state.evidence_catalog == {"C1": "src/requests/auth.py:85"}
    # every token delta was streamed live, in order
    assert emitter.partials == ["Auth is implemented here ", "[C1]", "."]
    # the LLM was handed the retrieved code content as grounding context
    assert "HTTPBasicAuth" in llm.calls[0][1]
    assert "[C1] -> `src/requests/auth.py:85`" in llm.calls[0][1]
    assert llm.calls[0][2] == "English"


async def test_synthesis_uses_original_followup_language_after_contextualization() -> None:
    emitter = _FakeEmitter()
    llm = _FakeLLM(["认证逻辑见 ", "[C1]", "。"])
    state = _search_state({"llm": llm, "emitter": emitter})
    state.query = "How does HTTPBasicAuth work?"
    state.raw_query = "它的认证逻辑是怎样的？"

    updated = await synthesize_node(state)

    assert updated.draft_answer == "认证逻辑见 [C1]。"
    assert llm.calls[0][0] == "How does HTTPBasicAuth work?"
    assert llm.calls[0][2] == "Chinese"


async def test_synthesis_falls_back_to_template_without_llm() -> None:
    emitter = _FakeEmitter()
    state = await synthesize_node(_search_state({"emitter": emitter}))
    answer = state.draft_answer or ""
    assert "`HTTPBasicAuth`" in answer
    assert "`src/requests/auth.py:85`" in answer
    # template path emits the whole answer as a single partial delta
    assert emitter.partials == [answer]


async def test_template_fallback_matches_a_chinese_question() -> None:
    emitter = _FakeEmitter()
    state = _search_state({"emitter": emitter})
    state.query = "认证逻辑是怎样的？"

    updated = await synthesize_node(state)
    answer = updated.draft_answer or ""

    assert answer.startswith("与 `认证逻辑是怎样的？` 最相关的代码结果：")
    assert "位于 `src/requests/auth.py:85`" in answer
    assert "Top code hits" not in answer


async def test_synthesis_degrades_to_template_when_llm_fails() -> None:
    emitter = _FakeEmitter()
    state = await synthesize_node(_search_state({"llm": _BoomLLM(), "emitter": emitter}))
    answer = state.draft_answer or ""
    assert "`src/requests/auth.py:85`" in answer
    # failed stream → template fallback, emitted once
    assert emitter.partials == [answer]


async def test_call_graph_context_separates_resolved_edges_from_source_expressions() -> None:
    emitter = _FakeEmitter()
    llm = _FakeLLM(["The resolved caller is shown here ", "[C3]", "."])
    state = AgentState(
        repo_id="11111111-1111-1111-1111-111111111111",
        query="Who calls it, and what does it call?",
        runtime={"llm": llm, "emitter": emitter},
        observations=[
            {
                "tool": "get_call_neighbors",
                "args": {"symbol": "HybridRetriever.retrieve", "direction": "both"},
                "cached": False,
                "result": {
                    "found": True,
                    "symbol": "HybridRetriever.retrieve",
                    "direction": "both",
                    "matches": [
                        {
                            "symbol": "src.retrieval.hybrid_search.HybridRetriever.retrieve",
                            "file_path": "src/retrieval/hybrid_search.py",
                            "line": 63,
                        }
                    ],
                    "callers": [
                        {
                            "symbol": "src.app.search",
                            "file_path": "src/app.py",
                            "line": 20,
                        }
                    ],
                    "callees": [],
                },
            },
            {
                "tool": "read_file",
                "args": {
                    "path": "src/retrieval/hybrid_search.py",
                    "line_range": [63, 143],
                },
                "cached": False,
                "result": {
                    "path": "src/retrieval/hybrid_search.py",
                    "line_range": [63, 143],
                    "content": "hits = self.faiss.retrieve(query)",
                },
            },
        ],
    )

    updated = await synthesize_node(state)
    context = llm.calls[0][1]

    assert updated.evidence_catalog is not None
    assert "callers (incoming calls)" in context
    assert "callees (outgoing calls)" in context
    assert "hits = self.faiss.retrieve(query)" in context
    assert "source-level evidence, not a resolved target" in context
