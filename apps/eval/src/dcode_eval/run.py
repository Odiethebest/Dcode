"""Evaluation CLI entry — implements DESIGN.md §2.4 + §4.4."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from dcode_eval.baselines import build_baseline
from dcode_eval.metrics.retrieval import mrr, ndcg_at_k, recall_at_k
from dcode_eval.questions import load_questions


async def run_eval(
    *,
    baseline_id: str,
    questions_path: str,
    output_dir: str,
    k: int,
) -> dict[str, Any]:
    baseline = build_baseline(baseline_id)
    questions = load_questions(questions_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_question_rows: list[dict[str, Any]] = []
    for question in questions:
        retrieved = await baseline.retrieve(question.repo_id, question.question, k)
        answer = await baseline.answer(question.repo_id, question.question)
        retrieved_chunk_ids = [str(chunk.chunk_id) for chunk in retrieved]
        retrieved_files = [chunk.file_path for chunk in retrieved]
        row = {
            "baseline": baseline_id,
            "question_id": question.id,
            "repo_id": question.repo_id,
            "question": question.question,
            "taxonomy": question.taxonomy,
            "source": question.source,
            "gt_chunk_ids": question.gt_chunk_ids,
            "gt_files": question.gt_files,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_files": retrieved_files,
            "answer": answer.answer,
            "citations": answer.citations,
            "groundedness": answer.groundedness,
            "recall_at_k": recall_at_k(retrieved_chunk_ids, set(question.gt_chunk_ids), k),
            "mrr": mrr(retrieved_chunk_ids, set(question.gt_chunk_ids)),
            "ndcg_at_k": ndcg_at_k(retrieved_chunk_ids, set(question.gt_chunk_ids), k),
        }
        per_question_rows.append(row)

    metrics = _aggregate_metrics(per_question_rows, baseline_id, k)
    taxonomy_breakdown = {
        taxonomy: _aggregate_metrics(
            [row for row in per_question_rows if row["taxonomy"] == taxonomy],
            baseline_id,
            k,
        )
        for taxonomy in ("L1", "L2", "L3")
    }

    _write_jsonl(out_dir / "per_question.jsonl", per_question_rows)
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "taxonomy_breakdown.json", taxonomy_breakdown)
    return {
        "per_question": per_question_rows,
        "metrics": metrics,
        "taxonomy_breakdown": taxonomy_breakdown,
    }


def _aggregate_metrics(rows: list[dict[str, Any]], baseline_id: str, k: int) -> dict[str, Any]:
    if not rows:
        return {
            "baseline": baseline_id,
            "questions": 0,
            "k": k,
            "recall_at_k": 0.0,
            "mrr": 0.0,
            "ndcg_at_k": 0.0,
            "groundedness": 0.0,
            "pairwise_win_rate": None,
        }
    return {
        "baseline": baseline_id,
        "questions": len(rows),
        "k": k,
        "recall_at_k": mean(row["recall_at_k"] for row in rows),
        "mrr": mean(row["mrr"] for row in rows),
        "ndcg_at_k": mean(row["ndcg_at_k"] for row in rows),
        "groundedness": mean(row["groundedness"] for row in rows),
        "pairwise_win_rate": None,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dcode-eval", description="Dcode evaluation harness")
    parser.add_argument(
        "--baseline",
        required=True,
        choices=["B0", "B1", "B2", "B3", "B4"],
        help="DESIGN.md §2.4.3 baseline tier to run",
    )
    parser.add_argument(
        "--questions",
        required=True,
        help="Path to questions JSONL (see apps/eval/src/dcode_eval/questions/README.md)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for per_question.jsonl / metrics.json / taxonomy_breakdown.json",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Retrieval cutoff k for Recall@k / nDCG@k",
    )
    args = parser.parse_args(argv)

    result = asyncio.run(
        run_eval(
            baseline_id=args.baseline,
            questions_path=args.questions,
            output_dir=args.output,
            k=args.k,
        )
    )
    metrics = result["metrics"]
    print(
        json.dumps(
            {
                "baseline": metrics["baseline"],
                "questions": metrics["questions"],
                "k": metrics["k"],
                "recall_at_k": metrics["recall_at_k"],
                "mrr": metrics["mrr"],
                "ndcg_at_k": metrics["ndcg_at_k"],
                "groundedness": metrics["groundedness"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
