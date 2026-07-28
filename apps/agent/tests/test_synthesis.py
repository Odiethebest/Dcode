"""LLM synthesis node — streams deltas live, and degrades to the template."""

from collections.abc import AsyncIterator
from typing import Any

from dcode_agent.graph import synthesize_node
from dcode_agent.state import AgentState


class _FakeLLM:
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.calls: list[tuple[str, str]] = []

    async def stream(self, *, question: str, context: str) -> AsyncIterator[str]:
        self.calls.append((question, context))
        for chunk in self.chunks:
            yield chunk


class _BoomLLM:
    async def stream(self, *, question: str, context: str) -> AsyncIterator[str]:
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
    llm = _FakeLLM(["Auth is in ", "`src/requests/auth.py:85`", "."])
    state = await synthesize_node(_search_state({"llm": llm, "emitter": emitter}))
    assert state.draft_answer == "Auth is in `src/requests/auth.py:85`."
    # every token delta was streamed live, in order
    assert emitter.partials == ["Auth is in ", "`src/requests/auth.py:85`", "."]
    # the LLM was handed the retrieved code content as grounding context
    assert "HTTPBasicAuth" in llm.calls[0][1]


async def test_synthesis_falls_back_to_template_without_llm() -> None:
    emitter = _FakeEmitter()
    state = await synthesize_node(_search_state({"emitter": emitter}))
    answer = state.draft_answer or ""
    assert "`HTTPBasicAuth`" in answer
    assert "`src/requests/auth.py:85`" in answer
    # template path emits the whole answer as a single partial delta
    assert emitter.partials == [answer]


async def test_synthesis_degrades_to_template_when_llm_fails() -> None:
    emitter = _FakeEmitter()
    state = await synthesize_node(_search_state({"llm": _BoomLLM(), "emitter": emitter}))
    answer = state.draft_answer or ""
    assert "`src/requests/auth.py:85`" in answer
    # failed stream → template fallback, emitted once
    assert emitter.partials == [answer]
