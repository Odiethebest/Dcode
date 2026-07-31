"""Baseline implementation tests."""

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult
from dcode_eval.baselines.bm25 import BM25Baseline
from dcode_eval.baselines.full_system import FullSystemBaseline
from dcode_eval.baselines.hybrid_rag import HybridRAGBaseline
from dcode_eval.baselines.vanilla_rag import VanillaRAGBaseline
from dcode_eval.settings import eval_settings
from dcode_shared.internal import INTERNAL_API_KEY_HEADER
from dcode_shared.schemas import Chunk, ScoreComponents


def _chunk() -> Chunk:
    return Chunk(
        chunk_id="05f376f2-fdb5-4c20-8ed1-80e9f3da8c55",
        file_path="src/requests/auth.py",
        symbol_name="HTTPBasicAuth",
        start_line=85,
        end_line=113,
        content="class HTTPBasicAuth(AuthBase): ...",
        score=1.0,
        score_components=ScoreComponents(dense=0.0, sparse=1.0, rerank=1.0),
    )


async def test_b1_b2_template_answers(monkeypatch) -> None:
    modes: list[str] = []

    async def fake_search(repo_id: str, query: str, k: int, *, mode: str) -> list[Chunk]:
        assert repo_id == "repo-1"
        assert query == "auth"
        assert k == 5
        modes.append(mode)
        return [_chunk()]

    monkeypatch.setattr("dcode_eval.baselines.common.internal_search", fake_search)

    b1 = await BM25Baseline().answer("repo-1", "auth")
    b2 = await VanillaRAGBaseline().answer("repo-1", "auth")
    assert "B1 sparse baseline" in b1.answer
    assert "B2 dense baseline" in b2.answer
    assert modes == ["sparse", "dense"]
    assert b1.citations == ["`src/requests/auth.py:85`"]


async def test_b3_uses_shared_agent_synthesis_without_graph(monkeypatch) -> None:
    async def fake_answer(repo_id: str, query: str) -> AnswerResult:
        assert repo_id == "repo-1"
        assert query == "auth"
        return AnswerResult(
            answer="Hybrid answer",
            citations=["`src/requests/auth.py:85`"],
            groundedness=1.0,
        )

    monkeypatch.setattr("dcode_eval.baselines.common.stream_hybrid_rag_answer", fake_answer)

    result = await HybridRAGBaseline().answer("repo-1", "auth")

    assert result.answer == "Hybrid answer"
    assert result.groundedness == 1.0


async def test_b4_full_system_uses_sse_answer(monkeypatch) -> None:
    async def fake_answer(repo_id: str, query: str) -> AnswerResult:
        assert repo_id == "repo-1"
        assert query == "auth"
        return AnswerResult(
            answer="Definition matches",
            citations=["`src/requests/auth.py:85`"],
            groundedness=1.0,
        )

    monkeypatch.setattr("dcode_eval.baselines.common.stream_full_system_answer", fake_answer)

    result = await FullSystemBaseline().answer("repo-1", "auth")

    assert result.answer == "Definition matches"
    assert result.groundedness == 1.0


async def test_stream_full_system_answer_targets_agent_and_bypasses_cache(monkeypatch) -> None:
    """B4 must call the agent's /internal/query (uncached), not the gateway /api/v1/query."""
    captured: dict[str, object] = {}

    class FakeStream:
        async def __aenter__(self) -> "FakeStream":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            for line in (
                "event: citation",
                'data: {"file_path": "src/requests/auth.py", "line": 85}',
                "",
                "event: final_answer",
                'data: {"answer": "Auth flow", "citations": [], "groundedness": 1.0}',
                "",
            ):
                yield line

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        def stream(self, method: str, url: str, *, json: object, headers: object) -> FakeStream:
            captured.update(method=method, url=url, json=json, headers=headers)
            return FakeStream()

    monkeypatch.setattr(common.httpx, "AsyncClient", FakeClient)

    result = await common.stream_full_system_answer("repo-1", "auth")

    assert captured["method"] == "POST"
    assert captured["url"] == f"{eval_settings.agent_base_url.rstrip('/')}/internal/query"
    assert "/api/v1/query" not in str(captured["url"])  # not the caching gateway path
    assert captured["headers"][INTERNAL_API_KEY_HEADER] == eval_settings.internal_api_key  # type: ignore[index]
    assert captured["json"] == {"repo_id": "repo-1", "query": "auth", "mode": "full"}
    assert result.answer == "Auth flow"
    assert result.citations == ["`src/requests/auth.py:85`"]
    assert result.groundedness == 1.0


async def test_stream_hybrid_rag_answer_selects_hybrid_only_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeStream:
        async def __aenter__(self) -> "FakeStream":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            for line in (
                "event: final_answer",
                'data: {"answer": "Hybrid answer", "citations": [], "groundedness": 1.0}',
                "",
            ):
                yield line

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        def stream(self, method: str, url: str, *, json: object, headers: object) -> FakeStream:
            captured.update(json=json)
            return FakeStream()

    monkeypatch.setattr(common.httpx, "AsyncClient", FakeClient)

    result = await common.stream_hybrid_rag_answer("repo-1", "auth")

    assert captured["json"] == {
        "repo_id": "repo-1",
        "query": "auth",
        "mode": "hybrid_only",
    }
    assert result.answer == "Hybrid answer"
