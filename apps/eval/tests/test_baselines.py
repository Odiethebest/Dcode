"""Baseline implementation tests."""

import pytest
from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult
from dcode_eval.baselines.bm25 import BM25Baseline
from dcode_eval.baselines.full_system import FullSystemBaseline
from dcode_eval.baselines.github_search import (
    _SECONDS_BETWEEN_CALLS,
    GithubSearchBaseline,
    MissingGithubTokenError,
    _item_to_chunk,
    _query_to_keywords,
)
from dcode_eval.baselines.hybrid_agent_no_graph import HybridAgentNoGraphBaseline
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


async def test_b1_still_answers_from_a_template(monkeypatch) -> None:
    """B1 is a retrieval reference, not a system arm, and is not in the decision."""
    modes: list[str] = []

    async def fake_search(repo_id: str, query: str, k: int, *, mode: str) -> list[Chunk]:
        assert repo_id == "repo-1"
        assert query == "auth"
        assert k == 5
        modes.append(mode)
        return [_chunk()]

    monkeypatch.setattr("dcode_eval.baselines.common.internal_search", fake_search)

    b1 = await BM25Baseline().answer("repo-1", "auth")
    assert "B1 sparse baseline" in b1.answer
    assert modes == ["sparse"]
    assert b1.citations == ["`src/requests/auth.py:85`"]
    # No citation events, so no verified final evidence, so the official rule
    # cannot apply to this arm. That is why it stays out of the H1 decision.
    assert b1.evidence == []


async def test_b2_answers_through_the_shared_agent_path(monkeypatch) -> None:
    """B2's groundedness must be measured, not the template's constant 1.0.

    This is what makes one scoring rule possible across the decision arms: a
    template emits no citations, so B2 could not be scored the way B4 is.
    """

    async def fake_answer(repo_id: str, query: str) -> AnswerResult:
        assert repo_id == "repo-1"
        assert query == "auth"
        return AnswerResult(answer="Dense answer", citations=[], groundedness=0.5)

    monkeypatch.setattr("dcode_eval.baselines.common.stream_dense_rag_answer", fake_answer)

    result = await VanillaRAGBaseline().answer("repo-1", "auth")

    assert result.answer == "Dense answer"
    assert result.groundedness == 0.5


async def test_b3_5_answers_through_the_agent_without_the_graph(monkeypatch) -> None:
    async def fake_answer(repo_id: str, query: str) -> AnswerResult:
        assert repo_id == "repo-1"
        assert query == "auth"
        return AnswerResult(answer="No-graph answer", citations=[], groundedness=1.0)

    monkeypatch.setattr("dcode_eval.baselines.common.stream_agent_no_graph_answer", fake_answer)

    result = await HybridAgentNoGraphBaseline().answer("repo-1", "auth")

    assert result.answer == "No-graph answer"


@pytest.mark.parametrize(
    ("stream_fn", "expected_mode"),
    [
        ("stream_dense_rag_answer", "dense_only"),
        ("stream_hybrid_rag_answer", "hybrid_only"),
        ("stream_agent_no_graph_answer", "agent_no_graph"),
        ("stream_full_system_answer", "full"),
    ],
)
async def test_each_arm_sends_its_own_agent_mode(monkeypatch, stream_fn, expected_mode) -> None:
    """The arm labels are only meaningful if the mode reaches the agent.

    Every arm shares one client helper, so a wiring slip here would silently
    run four identically-configured arms and make the whole ladder meaningless
    while every test that mocks at a higher level still passed.
    """
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
                'data: {"answer": "a", "citations": [], "groundedness": 1.0}',
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

    await getattr(common, stream_fn)("repo-1", "auth")

    assert captured["json"] == {"repo_id": "repo-1", "query": "auth", "mode": expected_mode}


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


# ---------------------------------------------------------------------------
# B0 — external, file-level, and not part of the H1 decision
# ---------------------------------------------------------------------------


async def test_b0_without_a_token_refuses_rather_than_scoring_zero(monkeypatch) -> None:
    """An empty result would be recorded as 0.000 across every metric.

    That reads as "GitHub Search found nothing", which is a claim about GitHub
    Search. Unmeasured is a blank; zero is an assertion. The baseline has to
    make the difference impossible to record by accident.
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(MissingGithubTokenError):
        await GithubSearchBaseline().retrieve("repo-1", "how are redirects resolved", 5)


def test_b0_chunk_ids_are_stable_per_path() -> None:
    """Random ids pinned every chunk-level metric at 0.000 by construction.

    A stable id still cannot match ground truth — B0 has no chunk-level result
    to give — but it makes two runs over the same file diff-able, so the
    emptiness is visibly deliberate rather than fresh noise each run.
    """
    item = {"path": "src/requests/sessions.py", "name": "sessions.py", "url": "u"}

    first = _item_to_chunk(item, 0)
    second = _item_to_chunk(item, 3)

    assert first.chunk_id == second.chunk_id
    assert first.chunk_id != _item_to_chunk({**item, "path": "src/requests/models.py"}, 0).chunk_id


def test_b0_rate_limit_respects_the_code_search_endpoint() -> None:
    """10 req/min, not the 30 the rest of the Search API allows.

    At the old 2s spacing a 33-question suite trips 403 partway through, and
    the questions after that point score zero — which looks like a baseline
    result rather than a rate limit.
    """
    assert _SECONDS_BETWEEN_CALLS >= 6.0


def test_b0_queries_never_contain_prose_scaffolding() -> None:
    """The baseline has to be given a query a competent user would type.

    GitHub ANDs every term. The first version sent "Explain" as a required
    term, which every architecture question in the suite opens with, and B0
    returned nothing for 9 of 12 of them. That measured our keyword extraction
    and would have been reported as GitHub Search's ceiling.
    """
    q = _query_to_keywords(
        "Explain how verify and client-certificate settings travel from "
        "Session.request to TLS connection verification."
    )
    lowered = q.lower().split()
    for junk in ("explain", "how", "from", "and", "to", "travel"):
        assert junk not in lowered, q


def test_b0_prefers_identifiers_over_prose() -> None:
    q = _query_to_keywords("Explain how Session.send selects an adapter and builds a Response")
    assert q.split()[0] == "Session.send"


def test_b0_sends_few_enough_terms_to_match_anything() -> None:
    """Every extra ANDed term removes results. Three identifiers is a query."""
    q = _query_to_keywords(
        "Explain the cookie lifecycle from Session request preparation "
        "through response persistence across the whole session stack"
    )
    assert 0 < len(q.split()) <= 3
