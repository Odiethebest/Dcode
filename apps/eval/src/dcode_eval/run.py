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


async def run_suite(
    *,
    baseline_ids: list[str],
    questions_path: str,
    output_dir: str,
    k: int,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suite_results: dict[str, Any] = {}
    for baseline_id in baseline_ids:
        suite_results[baseline_id] = await run_eval(
            baseline_id=baseline_id,
            questions_path=questions_path,
            output_dir=str(out_dir / baseline_id),
            k=k,
        )

    summary = {
        baseline_id: result["metrics"] for baseline_id, result in suite_results.items()
    }
    _write_json(out_dir / "suite_summary.json", summary)

    report: dict[str, Any] | None = None
    if {"B2", "B3", "B4"}.issubset(suite_results):
        report = _h1_report(suite_results)
        _write_json(out_dir / "h1_report.json", report)

    return {"suite": suite_results, "summary": summary, "h1_report": report}


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


def _h1_report(suite_results: dict[str, Any]) -> dict[str, Any]:
    threshold = 0.05
    compared_taxonomies = ("L2", "L3")
    comparisons: dict[str, Any] = {}
    supported = True

    for taxonomy in compared_taxonomies:
        b2 = suite_results["B2"]["taxonomy_breakdown"][taxonomy]
        b3 = suite_results["B3"]["taxonomy_breakdown"][taxonomy]
        b4 = suite_results["B4"]["taxonomy_breakdown"][taxonomy]
        b2_score = _composite_score(b2)
        b3_score = _composite_score(b3)
        b4_score = _composite_score(b4)
        margin_vs_b2 = b4_score - b2_score
        margin_vs_b3 = b4_score - b3_score
        taxonomy_supported = margin_vs_b2 >= threshold and margin_vs_b3 >= threshold
        supported = supported and taxonomy_supported
        comparisons[taxonomy] = {
            "B2_composite": b2_score,
            "B3_composite": b3_score,
            "B4_composite": b4_score,
            "margin_vs_B2": margin_vs_b2,
            "margin_vs_B3": margin_vs_b3,
            "supported": taxonomy_supported,
        }

    return {
        "decision": "supported" if supported else "unsupported",
        "threshold": threshold,
        "compared_taxonomies": list(compared_taxonomies),
        "comparisons": comparisons,
        "note": (
            "H1 is supported only if B4 beats both B2 and B3 by at least 0.05 "
            "composite points on both L2 and L3."
        ),
    }


def _composite_score(metrics: dict[str, Any]) -> float:
    return mean(
        [
            float(metrics["recall_at_k"]),
            float(metrics["mrr"]),
            float(metrics["ndcg_at_k"]),
            float(metrics["groundedness"]),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dcode-eval", description="Dcode evaluation harness")
    parser.add_argument(
        "--baseline",
        required=True,
        nargs="+",
        choices=["B0", "B1", "B2", "B3", "B4"],
        help="One or more DESIGN.md §2.4.3 baseline tiers to run",
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

    baselines = args.baseline
    if len(baselines) == 1:
        result = asyncio.run(
            run_eval(
                baseline_id=baselines[0],
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

    result = asyncio.run(
        run_suite(
            baseline_ids=baselines,
            questions_path=args.questions,
            output_dir=args.output,
            k=args.k,
        )
    )
    print(json.dumps(result["summary"], ensure_ascii=False))
    if result["h1_report"] is not None:
        print(json.dumps(result["h1_report"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
