"""Harness tests for the eval CLI core."""

import json
from pathlib import Path

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.run import run_eval
from dcode_shared.schemas import Chunk, ScoreComponents


class StubBaseline(Baseline):
    id = "B9"
    description = "stub"

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        assert repo_id == "repo-1"
        assert query == "What does auth do?"
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
