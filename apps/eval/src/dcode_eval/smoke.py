"""Offline smoke test for the evaluation harness."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from dcode_shared.schemas import Chunk, ScoreComponents

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.run import run_eval


class SmokeBaseline(Baseline):
    id = "B-smoke"
    description = "Offline smoke baseline for CI."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        _ = query
        assert repo_id == "repo-smoke"
        assert k == 3
        return [
            Chunk(
                chunk_id=UUID("05f376f2-fdb5-4c20-8ed1-80e9f3da8c55"),
                file_path="src/example.py",
                symbol_name="answer",
                start_line=1,
                end_line=3,
                content="def answer(): return 42",
                score=1.0,
                score_components=ScoreComponents(dense=0.0, sparse=1.0, rerank=1.0),
            )
        ]

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        _ = repo_id, query
        return AnswerResult(
            answer="Smoke top evidence:\n- `src/example.py:1` `answer`",
            citations=["`src/example.py:1`"],
            groundedness=1.0,
        )


async def _run_smoke() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="dcode-eval-smoke-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        questions_path = tmp_path / "questions.jsonl"
        output_dir = tmp_path / "out"
        questions_path.write_text(
            json.dumps(
                {
                    "id": "q-smoke-001",
                    "repo_id": "repo-smoke",
                    "question": "What is the answer helper?",
                    "taxonomy": "L1",
                    "gt_chunk_ids": ["05f376f2-fdb5-4c20-8ed1-80e9f3da8c55"],
                    "gt_files": ["src/example.py"],
                    "source": "smoke",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        import dcode_eval.run as run_module

        run_module_any = cast(Any, run_module)
        original_build_baseline = run_module_any.build_baseline
        run_module_any.build_baseline = lambda baseline_id: SmokeBaseline()
        try:
            result = await run_eval(
                baseline_id="B4",
                questions_path=str(questions_path),
                output_dir=str(output_dir),
                k=3,
            )
        finally:
            run_module_any.build_baseline = original_build_baseline

        metrics = result["metrics"]
        return {
            "baseline": metrics["baseline"],
            "questions": metrics["questions"],
            "recall_at_k": metrics["recall_at_k"],
            "groundedness": metrics["groundedness"],
            "output_dir": str(output_dir),
        }


def main() -> int:
    print(json.dumps(asyncio.run(_run_smoke()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
