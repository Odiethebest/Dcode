"""LLM synthesis node behaviour — opt-in, and degrades to the template."""

from typing import Any

from dcode_agent.graph import synthesize_node
from dcode_agent.state import AgentState


class _FakeLLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    async def synthesize(self, *, question: str, context: str) -> str:
        self.calls.append((question, context))
        return self.answer


class _BoomLLM:
    async def synthesize(self, *, question: str, context: str) -> str:
        raise RuntimeError("boom")


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


async def test_synthesis_uses_llm_when_configured() -> None:
    llm = _FakeLLM("Auth is handled in `src/requests/auth.py:85`.")
    state = await synthesize_node(_search_state({"llm": llm}))
    assert state.draft_answer == "Auth is handled in `src/requests/auth.py:85`."
    assert len(llm.calls) == 1
    # the LLM was handed the retrieved code content as grounding context
    assert "HTTPBasicAuth" in llm.calls[0][1]


async def test_synthesis_falls_back_to_template_without_llm() -> None:
    state = await synthesize_node(_search_state({}))
    answer = state.draft_answer or ""
    assert "`HTTPBasicAuth`" in answer
    assert "`src/requests/auth.py:85`" in answer


async def test_synthesis_degrades_to_template_when_llm_fails() -> None:
    state = await synthesize_node(_search_state({"llm": _BoomLLM()}))
    answer = state.draft_answer or ""
    assert "`src/requests/auth.py:85`" in answer
