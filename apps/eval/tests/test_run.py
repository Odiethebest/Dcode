"""Harness tests for the eval CLI core."""

import json
import logging
from pathlib import Path

import pytest
from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.run import _run_cli, run_eval, run_suite
from dcode_shared.events import CitationEvent
from dcode_shared.schemas import Chunk, ScoreComponents


class StubBaseline(Baseline):
    id = "B9"
    description = "stub"

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        assert repo_id == "repo-1"
        assert k == 5
        return [
            Chunk(
                chunk_id="05f376f2-fdb5-4c20-8ed1-80e9f3da8c55",
                file_path="src/requests/auth.py",
                symbol_name="HTTPBasicAuth",
                start_line=85,
                end_line=113,
                content="class HTTPBasicAuth(AuthBase): ...",
                score=1.0,
                score_components=ScoreComponents(dense=0.0, sparse=1.0, rerank=1.0),
            )
        ]

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        return AnswerResult(
            answer="B9 top evidence:\n- `src/requests/auth.py:85` `HTTPBasicAuth`",
            citations=["`src/requests/auth.py:85`"],
            groundedness=1.0,
        )


async def test_run_eval_writes_expected_artifacts(tmp_path: Path, monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger="dcode.eval.run")
    questions_path = tmp_path / "questions.jsonl"
    questions_path.write_text(
        json.dumps(
            {
                "id": "q-001",
                "repo_id": "repo-1",
                "question": "What does auth do?",
                "taxonomy": "L1",
                "gt_chunk_ids": ["05f376f2-fdb5-4c20-8ed1-80e9f3da8c55"],
                "gt_files": ["src/requests/auth.py"],
                "source": "manual",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("dcode_eval.run.build_baseline", lambda baseline_id: StubBaseline())

    result = await run_eval(
        baseline_id="B9",
        questions_path=str(questions_path),
        output_dir=str(tmp_path / "out"),
        k=5,
    )

    out_dir = tmp_path / "out"
    assert (out_dir / "per_question.jsonl").exists()
    assert (out_dir / "metrics.json").exists()
    assert (out_dir / "taxonomy_breakdown.json").exists()
    assert (out_dir / "run_config.json").exists()

    metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    run_config = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    assert metrics["baseline"] == "B9"
    assert run_config["baseline"] == "B9"
    assert run_config["corpus_revision"] is None
    assert run_config["sparse_retrieval"]["implementation"] == "okapi_bm25_v1"
    assert run_config["sparse_retrieval"]["document_fields"] == [
        "symbol_name",
        "file_path",
        "signature",
        "content",
    ]
    assert metrics["recall_at_k"] == 1.0
    assert metrics["groundedness"] == 1.0
    assert result["taxonomy_breakdown"]["L1"]["questions"] == 1
    assert any('"event": "eval_run_start"' in record.message for record in caplog.records)


async def test_run_eval_uses_resolved_repo_override(tmp_path: Path, monkeypatch) -> None:
    questions_path = tmp_path / "questions.jsonl"
    resolved_chunk_id = "11111111-1111-1111-1111-111111111111"
    override_repo_id = "22222222-2222-2222-2222-222222222222"
    questions_path.write_text(
        json.dumps(
            {
                "id": "q-001",
                "repo_id": "old-repo",
                "question": "What does auth do?",
                "taxonomy": "L1",
                "gt_chunk_ids": ["33333333-3333-3333-3333-333333333333"],
                "gt_targets": [
                    {
                        "file_path": "src/requests/auth.py",
                        "symbol_name": "HTTPBasicAuth",
                        "start_line": 85,
                    }
                ],
                "gt_files": ["src/requests/auth.py"],
                "source": "manual",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class OverrideBaseline(Baseline):
        id = "B9"
        description = "override stub"

        async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
            assert repo_id == override_repo_id
            return [
                Chunk(
                    chunk_id=resolved_chunk_id,
                    file_path="src/requests/auth.py",
                    symbol_name="HTTPBasicAuth",
                    start_line=85,
                    end_line=113,
                    content="class HTTPBasicAuth(AuthBase): ...",
                    score=1.0,
                    score_components=ScoreComponents(dense=0.0, sparse=1.0, rerank=1.0),
                )
            ]

        async def answer(self, repo_id: str, query: str) -> AnswerResult:
            assert repo_id == override_repo_id
            return AnswerResult(answer="resolved", citations=[], groundedness=1.0)

    async def fake_resolve_questions(questions, *, repo_id_override):
        assert repo_id_override == override_repo_id
        assert questions[0].gt_targets[0].symbol_name == "HTTPBasicAuth"
        return [
            questions[0].model_copy(
                update={"repo_id": override_repo_id, "gt_chunk_ids": [resolved_chunk_id]}
            )
        ]

    monkeypatch.setattr("dcode_eval.run.build_baseline", lambda baseline_id: OverrideBaseline())
    monkeypatch.setattr("dcode_eval.run.resolve_questions", fake_resolve_questions)

    result = await run_eval(
        baseline_id="B9",
        questions_path=str(questions_path),
        output_dir=str(tmp_path / "out"),
        k=5,
        repo_id_override=override_repo_id,
        corpus_revision=42,
    )

    row = result["per_question"][0]
    run_config = json.loads((tmp_path / "out" / "run_config.json").read_text(encoding="utf-8"))
    assert row["repo_id"] == override_repo_id
    assert row["gt_chunk_ids"] == [resolved_chunk_id]
    assert row["recall_at_k"] == 1.0
    assert run_config["corpus_revision"] == 42


async def test_b4_scores_final_verified_evidence_and_keeps_candidate_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    questions_path = tmp_path / "questions.jsonl"
    gt_chunk_id = "11111111-1111-1111-1111-111111111111"
    noise_chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    questions_path.write_text(
        json.dumps(
            {
                "id": "q-l2",
                "repo_id": "repo-1",
                "question": "How does the flow work?",
                "taxonomy": "L2",
                "gt_chunk_ids": [gt_chunk_id],
                "gt_files": ["src/requests/api.py"],
                "source": "manual",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class FinalEvidenceBaseline(Baseline):
        id = "B4"
        description = "final evidence stub"

        async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
            return [
                Chunk(
                    chunk_id=noise_chunk_id,
                    file_path="tests/test_requests.py",
                    symbol_name="noise",
                    start_line=1,
                    end_line=2,
                    content="noise",
                    score=0.1,
                    score_components=ScoreComponents(dense=0.0, sparse=0.1, rerank=0.1),
                )
            ]

        async def answer(self, repo_id: str, query: str) -> AnswerResult:
            citation = CitationEvent(
                symbol="requests.api.request",
                file_path="src/requests/api.py",
                line=24,
                verified=True,
                chunk_id=gt_chunk_id,
                evidence_id="C1",
                origins=["get_call_neighbors"],
            )
            return AnswerResult(
                answer="Flow [C1]",
                citations=["`src/requests/api.py:24`", "`src/requests/api.py:24`"],
                groundedness=1.0,
                evidence=[citation, citation],
            )

    monkeypatch.setattr(
        "dcode_eval.run.build_baseline", lambda baseline_id: FinalEvidenceBaseline()
    )

    result = await run_eval(
        baseline_id="B4",
        questions_path=str(questions_path),
        output_dir=str(tmp_path / "out"),
        k=5,
    )

    row = result["per_question"][0]
    assert row["candidate_recall_at_k"] == 0.0
    assert row["recall_at_k"] == 1.0
    assert row["scoring_source"] == "final_verified_evidence"
    assert row["final_evidence_chunk_ids"] == [gt_chunk_id]
    assert row["structural_evidence_chunk_ids"] == [gt_chunk_id]
    assert row["new_gt_hits_from_structural_evidence"] == [gt_chunk_id]
    assert result["metrics"]["candidate_recall_at_k"] == 0.0
    assert result["metrics"]["recall_at_k"] == 1.0


async def test_b4_caps_final_evidence_and_mrr_at_k(tmp_path: Path, monkeypatch) -> None:
    questions_path = tmp_path / "questions.jsonl"
    gt_chunk_id = "11111111-1111-1111-1111-111111111111"
    noise_chunk_ids = [f"aaaaaaaa-aaaa-aaaa-aaaa-{index:012d}" for index in range(1, 6)]
    questions_path.write_text(
        json.dumps(
            {
                "id": "q-l3",
                "repo_id": "repo-1",
                "question": "Explain the architecture.",
                "taxonomy": "L3",
                "gt_chunk_ids": [gt_chunk_id],
                "gt_files": ["src/requests/api.py"],
                "source": "manual",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class LongFinalEvidenceBaseline(Baseline):
        id = "B4"
        description = "long final evidence stub"

        async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
            return []

        async def answer(self, repo_id: str, query: str) -> AnswerResult:
            evidence = [
                CitationEvent(
                    symbol=f"noise_{index}",
                    file_path="src/noise.py",
                    line=index,
                    verified=True,
                    chunk_id=chunk_id,
                    origins=["search_code"],
                )
                for index, chunk_id in enumerate(noise_chunk_ids, start=1)
            ]
            evidence.append(
                CitationEvent(
                    symbol="requests.api.request",
                    file_path="src/requests/api.py",
                    line=24,
                    verified=True,
                    chunk_id=gt_chunk_id,
                    origins=["get_call_neighbors"],
                )
            )
            return AnswerResult(
                answer="Long evidence answer",
                citations=[f"`{citation.file_path}:{citation.line}`" for citation in evidence],
                groundedness=1.0,
                evidence=evidence,
            )

    monkeypatch.setattr(
        "dcode_eval.run.build_baseline",
        lambda baseline_id: LongFinalEvidenceBaseline(),
    )

    result = await run_eval(
        baseline_id="B4",
        questions_path=str(questions_path),
        output_dir=str(tmp_path / "out"),
        k=5,
    )

    row = result["per_question"][0]
    assert row["final_evidence_chunk_ids"] == [*noise_chunk_ids, gt_chunk_id]
    assert row["final_evidence_scored_chunk_ids"] == noise_chunk_ids
    assert row["scored_chunk_ids"] == noise_chunk_ids
    assert row["final_evidence_mrr"] == 0.0
    assert row["mrr"] == 0.0


async def test_run_suite_writes_h1_report(tmp_path: Path, monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger="dcode.eval.run")
    questions_path = tmp_path / "questions.jsonl"
    questions_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "q-l2",
                        "repo_id": "repo-1",
                        "question": "How does auth flow work?",
                        "taxonomy": "L2",
                        "gt_chunk_ids": ["05f376f2-fdb5-4c20-8ed1-80e9f3da8c55"],
                        "gt_files": ["src/requests/auth.py"],
                        "source": "manual",
                    }
                ),
                json.dumps(
                    {
                        "id": "q-l3",
                        "repo_id": "repo-1",
                        "question": "Explain end-to-end auth.",
                        "taxonomy": "L3",
                        "gt_chunk_ids": ["05f376f2-fdb5-4c20-8ed1-80e9f3da8c55"],
                        "gt_files": ["src/requests/auth.py"],
                        "source": "manual",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class RankedStubBaseline(StubBaseline):
        def __init__(self, baseline_id: str) -> None:
            self.id = baseline_id

        async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
            if self.id == "B4":
                return await StubBaseline.retrieve(self, repo_id, query, k)
            return [
                Chunk(
                    chunk_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    file_path="tests/test_requests.py",
                    symbol_name="noise",
                    start_line=1,
                    end_line=2,
                    content="noise",
                    score=0.1,
                    score_components=ScoreComponents(dense=0.0, sparse=0.1, rerank=0.1),
                )
            ]

        async def answer(self, repo_id: str, query: str) -> AnswerResult:
            if self.id == "B4":
                return await super().answer(repo_id, query)
            return AnswerResult(answer="weak baseline", citations=[], groundedness=0.0)

    monkeypatch.setattr(
        "dcode_eval.run.build_baseline",
        lambda baseline_id: RankedStubBaseline(baseline_id),
    )

    result = await run_suite(
        baseline_ids=["B2", "B3", "B4"],
        questions_path=str(questions_path),
        output_dir=str(tmp_path / "suite"),
        k=5,
    )

    assert (tmp_path / "suite" / "suite_summary.json").exists()
    assert (tmp_path / "suite" / "h1_report.json").exists()
    assert (tmp_path / "suite" / "run_config.json").exists()
    suite_config = json.loads((tmp_path / "suite" / "run_config.json").read_text(encoding="utf-8"))
    assert suite_config["corpus_revision"] is None
    assert suite_config["sparse_retrieval"]["tokenizer"] == "dcode_source_code_v1"
    assert result["h1_report"]["decision"] == "supported"
    assert any('"event": "eval_suite_start"' in record.message for record in caplog.records)


async def test_cli_rejects_a_corpus_that_changes_during_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revisions = iter([7, 8])

    async def fake_revision(_: str | None) -> int:
        return next(revisions)

    async def fake_run_eval(**_: object) -> dict[str, object]:
        return {"metrics": {}}

    monkeypatch.setattr("dcode_eval.run._read_corpus_revision", fake_revision)
    monkeypatch.setattr("dcode_eval.run.run_eval", fake_run_eval)

    with pytest.raises(RuntimeError, match="started at revision 7, ended at 8"):
        await _run_cli(
            baselines=["B1"],
            questions_path="unused.jsonl",
            output_dir="unused",
            k=5,
            repo_id_override="11111111-1111-1111-1111-111111111111",
        )


# ---------------------------------------------------------------------------
# uniform_final_verified_evidence_v2
# ---------------------------------------------------------------------------


def _one_question(path: Path, gt_chunk_id: str, taxonomy: str = "L2") -> None:
    path.write_text(
        json.dumps(
            {
                "id": f"q-{taxonomy.lower()}",
                "repo_id": "repo-1",
                "question": "How does the flow work?",
                "taxonomy": taxonomy,
                "gt_chunk_ids": [gt_chunk_id],
                "gt_files": ["src/requests/api.py"],
                "source": "manual",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _agent_arm(baseline_id: str, gt_chunk_id: str, noise_chunk_id: str) -> Baseline:
    class AgentArm(Baseline):
        id = baseline_id
        description = "agent arm stub"

        async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
            return [
                Chunk(
                    chunk_id=noise_chunk_id,
                    file_path="tests/test_requests.py",
                    symbol_name="noise",
                    start_line=1,
                    end_line=2,
                    content="noise",
                    score=0.1,
                    score_components=ScoreComponents(dense=0.0, sparse=0.1, rerank=0.1),
                )
            ]

        async def answer(self, repo_id: str, query: str) -> AnswerResult:
            return AnswerResult(
                answer="Flow [C1]",
                citations=["`src/requests/api.py:24`"],
                groundedness=1.0,
                evidence=[
                    CitationEvent(
                        symbol="requests.api.request",
                        file_path="src/requests/api.py",
                        line=24,
                        verified=True,
                        chunk_id=gt_chunk_id,
                        evidence_id="C1",
                        origins=["search_code"],
                    )
                ],
            )

    return AgentArm()


@pytest.mark.parametrize("baseline_id", ["B2", "B3", "B3.5", "B4"])
async def test_every_agent_arm_is_scored_on_final_evidence(
    tmp_path: Path, monkeypatch, baseline_id
) -> None:
    """The v1 protocol applied this rule to B4 alone.

    That asymmetry, not the systems, decided the 2026-07-31 L3 result: B4 - B3
    was +0.045 under mixed scoring and +0.051 when B3 was scored the same way,
    which straddles the 0.05 bar. Every decision arm now uses one rule.
    """
    gt_chunk_id = "11111111-1111-1111-1111-111111111111"
    noise_chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _one_question(tmp_path / "questions.jsonl", gt_chunk_id)

    monkeypatch.setattr(
        "dcode_eval.run.build_baseline",
        lambda bid: _agent_arm(bid, gt_chunk_id, noise_chunk_id),
    )

    result = await run_eval(
        baseline_id=baseline_id,
        questions_path=str(tmp_path / "questions.jsonl"),
        output_dir=str(tmp_path / "out"),
        k=5,
    )

    row = result["per_question"][0]
    assert row["scoring_source"] == "final_verified_evidence"
    assert row["candidate_recall_at_k"] == 0.0
    assert row["recall_at_k"] == 1.0


@pytest.mark.parametrize("baseline_id", ["B0", "B1"])
async def test_retrieval_reference_arms_keep_candidate_scoring(
    tmp_path: Path, monkeypatch, baseline_id
) -> None:
    """B0/B1 answer from a template and emit no citations.

    The uniform rule cannot apply to them, so they stay retrieval references —
    and are excluded from the H1 decision rather than scored by a second rule
    inside it.
    """
    gt_chunk_id = "11111111-1111-1111-1111-111111111111"
    _one_question(tmp_path / "questions.jsonl", gt_chunk_id)

    class TemplateArm(Baseline):
        id = baseline_id
        description = "template stub"

        async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
            return [
                Chunk(
                    chunk_id=gt_chunk_id,
                    file_path="src/requests/api.py",
                    symbol_name="request",
                    start_line=24,
                    end_line=71,
                    content="def request(): ...",
                    score=1.0,
                    score_components=ScoreComponents(dense=0.0, sparse=1.0, rerank=1.0),
                )
            ]

        async def answer(self, repo_id: str, query: str) -> AnswerResult:
            return AnswerResult(answer="template", citations=[], groundedness=1.0)

    monkeypatch.setattr("dcode_eval.run.build_baseline", lambda bid: TemplateArm())

    result = await run_eval(
        baseline_id=baseline_id,
        questions_path=str(tmp_path / "questions.jsonl"),
        output_dir=str(tmp_path / "out"),
        k=5,
    )

    row = result["per_question"][0]
    assert row["scoring_source"] == "retrieved_top_k"
    assert row["recall_at_k"] == 1.0
    assert row["final_evidence_chunk_ids"] == []


async def test_b3_5_is_reported_as_a_diagnostic_and_never_in_the_decision(
    tmp_path: Path, monkeypatch
) -> None:
    gt_chunk_id = "11111111-1111-1111-1111-111111111111"
    noise_chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _one_question(tmp_path / "questions.jsonl", gt_chunk_id)

    monkeypatch.setattr(
        "dcode_eval.run.build_baseline",
        lambda bid: _agent_arm(bid, gt_chunk_id, noise_chunk_id),
    )

    result = await run_suite(
        baseline_ids=["B2", "B3", "B3.5", "B4"],
        questions_path=str(tmp_path / "questions.jsonl"),
        output_dir=str(tmp_path / "out"),
        k=5,
    )

    report = result["h1_report"]
    # The decision reads B2/B3/B4 only. Promoting the diagnostic arm into the
    # rule would be changing the pass criteria after the fact.
    assert set(report["comparisons"]["L2"]) == {
        "B2_composite",
        "B3_composite",
        "B4_composite",
        "margin_vs_B2",
        "margin_vs_B3",
        "supported",
    }
    diagnostics = report["diagnostics"]["per_taxonomy"]["L2"]
    assert "graph_margin_B4_vs_B3.5" in diagnostics
    assert "agent_loop_margin_B3.5_vs_B3" in diagnostics
    assert report["scoring_protocol"] == "uniform_final_verified_evidence_v2"


async def test_h1_report_omits_diagnostics_when_b3_5_was_not_run(
    tmp_path: Path, monkeypatch
) -> None:
    gt_chunk_id = "11111111-1111-1111-1111-111111111111"
    noise_chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _one_question(tmp_path / "questions.jsonl", gt_chunk_id)

    monkeypatch.setattr(
        "dcode_eval.run.build_baseline",
        lambda bid: _agent_arm(bid, gt_chunk_id, noise_chunk_id),
    )

    result = await run_suite(
        baseline_ids=["B2", "B3", "B4"],
        questions_path=str(tmp_path / "questions.jsonl"),
        output_dir=str(tmp_path / "out"),
        k=5,
    )

    assert "diagnostics" not in result["h1_report"]
