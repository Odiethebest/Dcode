"""Baseline implementation tests."""

from dcode_eval.baselines.base import AnswerResult
from dcode_eval.baselines.bm25 import BM25Baseline
from dcode_eval.baselines.full_system import FullSystemBaseline
from dcode_eval.baselines.hybrid_rag import HybridRAGBaseline
from dcode_eval.baselines.vanilla_rag import VanillaRAGBaseline
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


async def test_b1_b2_b3_template_answers(monkeypatch) -> None:
    async def fake_search(repo_id: str, query: str, k: int) -> list[Chunk]:
        assert repo_id == "repo-1"
        assert query == "auth"
        assert k == 5
        return [_chunk()]

    monkeypatch.setattr("dcode_eval.baselines.common.internal_search", fake_search)

    b1 = await BM25Baseline().answer("repo-1", "auth")
    b2 = await VanillaRAGBaseline().answer("repo-1", "auth")
    b3 = await HybridRAGBaseline().answer("repo-1", "auth")

    assert "B1 sparse baseline" in b1.answer
    assert "B2 dense baseline" in b2.answer
    assert "B3 hybrid baseline" in b3.answer
    assert b1.citations == ["`src/requests/auth.py:85`"]


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
