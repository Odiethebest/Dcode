"""Harness tests for the eval CLI core."""

import json
from pathlib import Path

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.run import run_eval, run_suite
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


async def test_run_eval_writes_expected_artifacts(tmp_path: Path, monkeypatch) -> None:
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

    metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["baseline"] == "B9"
    assert metrics["recall_at_k"] == 1.0
    assert metrics["groundedness"] == 1.0
    assert result["taxonomy_breakdown"]["L1"]["questions"] == 1


async def test_run_suite_writes_h1_report(tmp_path: Path, monkeypatch) -> None:
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
    assert result["h1_report"]["decision"] == "supported"
