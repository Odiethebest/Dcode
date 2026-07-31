"""CLI for reproducible baseline evaluation and H1 report generation."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import UUID

from dcode_shared.bm25 import bm25_run_config
from dcode_shared.db.models import Repo
from dcode_shared.db.session import SessionLocal
from dcode_shared.observability import log_event

from dcode_eval.baselines import AGENT_BASELINES, build_baseline
from dcode_eval.metrics.retrieval import mrr, ndcg_at_k, recall_at_k
from dcode_eval.questions import load_questions
from dcode_eval.questions.resolve import resolve_questions

logger = logging.getLogger("dcode.eval.run")

# v2 differs from v1 in one respect, and it is the respect the previous verdict
# turned on: the official metric is now the same rule for every arm that can
# produce evidence, instead of verified-final-evidence for B4 and retrieved
# top-k for everyone else.
#
# Under v1 the 2026-07-31 run reported B4 - B3 at +0.083 on L2 and +0.045 on L3
# and so returned `unsupported`; scoring B3 by B4's rule gave +0.057 and +0.051,
# which would have cleared both. A decision that moves depending on which arm is
# measured how is not a decision. v2 removes the choice rather than resolving it
# in either direction.
#
# Pre-registered before the arms that require it (B2 via dense_only, B3.5) had
# ever been run, so no number influenced the selection between the two rules.
_SCORING_PROTOCOL = "uniform_final_verified_evidence_v2"
_STRUCTURAL_EVIDENCE_ORIGINS = {
    "find_definition",
    "find_references",
    "get_call_neighbors",
    "get_dependencies",
    "get_dependents",
    "get_file_outline",
}


async def run_eval(
    *,
    baseline_id: str,
    questions_path: str,
    output_dir: str,
    k: int,
    repo_id_override: str | None = None,
    corpus_revision: int | None = None,
) -> dict[str, Any]:
    baseline = build_baseline(baseline_id)
    questions = await resolve_questions(
        load_questions(questions_path), repo_id_override=repo_id_override
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_config = {
        "mode": "single",
        "baseline": baseline_id,
        "questions_path": questions_path,
        "output_dir": output_dir,
        "k": k,
        "repo_id_override": repo_id_override,
        "corpus_revision": corpus_revision,
        "scoring_protocol": _SCORING_PROTOCOL,
        "sparse_retrieval": bm25_run_config(),
    }
    _write_json(out_dir / "run_config.json", run_config)
    log_event(logger, "eval_run_start", **run_config)

    per_question_rows: list[dict[str, Any]] = []
    for question in questions:
        retrieved = await baseline.retrieve(question.repo_id, question.question, k)
        answer = await baseline.answer(question.repo_id, question.question)
        retrieved_chunk_ids = [str(chunk.chunk_id) for chunk in retrieved]
        retrieved_files = [chunk.file_path for chunk in retrieved]
        final_evidence_chunk_ids = _verified_evidence_chunk_ids(answer)
        candidate_scored_chunk_ids = retrieved_chunk_ids[:k]
        final_evidence_scored_chunk_ids = final_evidence_chunk_ids[:k]
        # One rule for every arm that answers through the agent. B0/B1 answer
        # from a template and emit no citations, so the rule cannot apply to
        # them; they stay retrieval references and are not in the H1 decision.
        scores_final_evidence = baseline_id in AGENT_BASELINES
        scored_chunk_ids = (
            final_evidence_scored_chunk_ids
            if scores_final_evidence
            else candidate_scored_chunk_ids
        )
        gt_chunk_ids = set(question.gt_chunk_ids)
        structural_evidence_chunk_ids = _structural_evidence_chunk_ids(
            answer,
            exclude=set(retrieved_chunk_ids),
        )
        row = {
            "baseline": baseline_id,
            "question_id": question.id,
            "repo_id": question.repo_id,
            "question": question.question,
            "taxonomy": question.taxonomy,
            "source": question.source,
            "gt_chunk_ids": question.gt_chunk_ids,
            "gt_targets": [target.model_dump(exclude_none=True) for target in question.gt_targets],
            "gt_files": question.gt_files,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_files": retrieved_files,
            "final_evidence": [
                citation.model_dump(mode="json", exclude_none=True) for citation in answer.evidence
            ],
            "final_evidence_chunk_ids": final_evidence_chunk_ids,
            "final_evidence_scored_chunk_ids": final_evidence_scored_chunk_ids,
            "structural_evidence_chunk_ids": structural_evidence_chunk_ids,
            "new_gt_hits_from_structural_evidence": [
                chunk_id for chunk_id in structural_evidence_chunk_ids if chunk_id in gt_chunk_ids
            ],
            "scored_chunk_ids": scored_chunk_ids,
            "scoring_source": (
                "final_verified_evidence" if scores_final_evidence else "retrieved_top_k"
            ),
            "answer": answer.answer,
            "citations": answer.citations,
            "groundedness": answer.groundedness,
            "candidate_recall_at_k": recall_at_k(candidate_scored_chunk_ids, gt_chunk_ids, k),
            "candidate_mrr": mrr(candidate_scored_chunk_ids, gt_chunk_ids),
            "candidate_ndcg_at_k": ndcg_at_k(candidate_scored_chunk_ids, gt_chunk_ids, k),
            "final_evidence_recall_at_k": recall_at_k(
                final_evidence_scored_chunk_ids, gt_chunk_ids, k
            ),
            "final_evidence_mrr": mrr(final_evidence_scored_chunk_ids, gt_chunk_ids),
            "final_evidence_ndcg_at_k": ndcg_at_k(final_evidence_scored_chunk_ids, gt_chunk_ids, k),
            "recall_at_k": recall_at_k(scored_chunk_ids, gt_chunk_ids, k),
            "mrr": mrr(scored_chunk_ids, gt_chunk_ids),
            "ndcg_at_k": ndcg_at_k(scored_chunk_ids, gt_chunk_ids, k),
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
    log_event(
        logger,
        "eval_run_complete",
        baseline=baseline_id,
        questions=len(per_question_rows),
        k=k,
        output_dir=output_dir,
    )
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
    repo_id_override: str | None = None,
    corpus_revision: int | None = None,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_config = {
        "mode": "suite",
        "baselines": baseline_ids,
        "questions_path": questions_path,
        "output_dir": output_dir,
        "k": k,
        "repo_id_override": repo_id_override,
        "corpus_revision": corpus_revision,
        "scoring_protocol": _SCORING_PROTOCOL,
        "sparse_retrieval": bm25_run_config(),
    }
    _write_json(out_dir / "run_config.json", run_config)
    log_event(logger, "eval_suite_start", **run_config)
    suite_results: dict[str, Any] = {}
    for baseline_id in baseline_ids:
        suite_results[baseline_id] = await run_eval(
            baseline_id=baseline_id,
            questions_path=questions_path,
            output_dir=str(out_dir / baseline_id),
            k=k,
            repo_id_override=repo_id_override,
            corpus_revision=corpus_revision,
        )

    summary = {baseline_id: result["metrics"] for baseline_id, result in suite_results.items()}
    _write_json(out_dir / "suite_summary.json", summary)

    report: dict[str, Any] | None = None
    if {"B2", "B3", "B4"}.issubset(suite_results):
        report = _h1_report(suite_results)
        _write_json(out_dir / "h1_report.json", report)

    log_event(logger, "eval_suite_complete", baselines=baseline_ids, output_dir=output_dir, k=k)
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
            "candidate_recall_at_k": 0.0,
            "candidate_mrr": 0.0,
            "candidate_ndcg_at_k": 0.0,
            "final_evidence_recall_at_k": 0.0,
            "final_evidence_mrr": 0.0,
            "final_evidence_ndcg_at_k": 0.0,
            "groundedness": 0.0,
            "answers_without_citations": 0,
            "pairwise_win_rate": None,
        }

    def average(key: str, *, fallback: str | None = None) -> float:
        values: list[float] = []
        for row in rows:
            if key in row:
                value = row[key]
            elif fallback is not None:
                value = row.get(fallback, 0.0)
            else:
                value = 0.0
            values.append(float(value))
        return mean(values)

    return {
        "baseline": baseline_id,
        "questions": len(rows),
        "k": k,
        "recall_at_k": average("recall_at_k"),
        "mrr": average("mrr"),
        "ndcg_at_k": average("ndcg_at_k"),
        "candidate_recall_at_k": average("candidate_recall_at_k", fallback="recall_at_k"),
        "candidate_mrr": average("candidate_mrr", fallback="mrr"),
        "candidate_ndcg_at_k": average("candidate_ndcg_at_k", fallback="ndcg_at_k"),
        "final_evidence_recall_at_k": average("final_evidence_recall_at_k"),
        "final_evidence_mrr": average("final_evidence_mrr"),
        "final_evidence_ndcg_at_k": average("final_evidence_ndcg_at_k"),
        "groundedness": average("groundedness"),
        # Required alongside groundedness, not optional beside it. An answer citing
        # nothing scores 0.0 (dcode_agent.groundedness.verify), which is the same
        # number an answer whose every citation failed would get — two different
        # failures that the mean cannot tell apart. This count is the only thing
        # that separates them once the scores are averaged, and without it a
        # baseline could post a low groundedness for the honest reason or for the
        # useless one and read identically.
        "answers_without_citations": sum(1 for row in rows if not row["citations"]),
        "pairwise_win_rate": None,
    }


def _verified_evidence_chunk_ids(answer: Any) -> list[str]:
    """Verified final evidence, deduped by chunk after mapping and in answer order."""

    chunk_ids: list[str] = []
    for citation in answer.evidence:
        if not citation.verified or citation.chunk_id is None:
            continue
        chunk_id = str(citation.chunk_id)
        if chunk_id not in chunk_ids:
            chunk_ids.append(chunk_id)
    return chunk_ids


def _structural_evidence_chunk_ids(answer: Any, *, exclude: set[str]) -> list[str]:
    """Final evidence newly surfaced by a graph/structure tool."""

    chunk_ids: list[str] = []
    for citation in answer.evidence:
        if (
            not citation.verified
            or citation.chunk_id is None
            or not _STRUCTURAL_EVIDENCE_ORIGINS.intersection(citation.origins)
        ):
            continue
        chunk_id = str(citation.chunk_id)
        if chunk_id in exclude or chunk_id in chunk_ids:
            continue
        chunk_ids.append(chunk_id)
    return chunk_ids


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _read_corpus_revision(repo_id: str | None) -> int | None:
    """Read the exact indexed generation recorded by a CLI evaluation run."""

    if repo_id is None:
        return None
    try:
        repo_uuid = UUID(repo_id)
    except ValueError as exc:
        raise ValueError("--repo-id must be a UUID when recording corpus revision") from exc

    async with SessionLocal() as db:
        repo = await db.get(Repo, repo_uuid)
    if repo is None:
        raise ValueError(f"cannot record corpus revision for unknown repo_id: {repo_id}")
    return repo.index_revision


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

    report: dict[str, Any] = {
        "decision": "supported" if supported else "unsupported",
        "threshold": threshold,
        "scoring_protocol": _SCORING_PROTOCOL,
        "compared_taxonomies": list(compared_taxonomies),
        "comparisons": comparisons,
        "note": (
            "H1 is supported only if B4 beats both B2 and B3 by at least 0.05 "
            "composite points on both L2 and L3."
        ),
    }

    diagnostics = _graph_ablation(suite_results, compared_taxonomies)
    if diagnostics is not None:
        report["diagnostics"] = diagnostics
    return report


def _graph_ablation(
    suite_results: dict[str, Any],
    taxonomies: tuple[str, ...],
) -> dict[str, Any] | None:
    """B3.5 margins, reported beside the decision and excluded from it.

    ``B4 - B3`` moves when either the graph or multi-step reading moves, so on
    its own it cannot say which. ``B4 - B3.5`` holds the agent fixed and removes
    only the graph, which is the hypothesis. This is recorded as a diagnostic
    because promoting an arm into the decision rule would be changing the pass
    criteria after the fact — the one thing the standing commitments forbid.
    """
    if "B3.5" not in suite_results:
        return None

    per_level: dict[str, Any] = {}
    for taxonomy in taxonomies:
        b3 = _composite_score(suite_results["B3"]["taxonomy_breakdown"][taxonomy])
        b35 = _composite_score(suite_results["B3.5"]["taxonomy_breakdown"][taxonomy])
        b4 = _composite_score(suite_results["B4"]["taxonomy_breakdown"][taxonomy])
        per_level[taxonomy] = {
            "B3_composite": b3,
            "B3.5_composite": b35,
            "B4_composite": b4,
            # The call graph alone.
            "graph_margin_B4_vs_B3.5": b4 - b35,
            # Multi-step reading without a graph.
            "agent_loop_margin_B3.5_vs_B3": b35 - b3,
        }

    return {
        "about": (
            "Diagnostic only. B3.5 is B4 with the call-graph and reference tools "
            "disabled and everything else identical. These margins decompose "
            "B4 - B3 into a graph term and an agent-loop term; they do not enter "
            "the H1 decision."
        ),
        "per_taxonomy": per_level,
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


async def _run_cli(
    *,
    baselines: list[str],
    questions_path: str,
    output_dir: str,
    k: int,
    repo_id_override: str | None,
) -> dict[str, Any]:
    """Record and use one corpus generation inside one event loop."""

    corpus_revision = await _read_corpus_revision(repo_id_override)
    if len(baselines) == 1:
        result = await run_eval(
            baseline_id=baselines[0],
            questions_path=questions_path,
            output_dir=output_dir,
            k=k,
            repo_id_override=repo_id_override,
            corpus_revision=corpus_revision,
        )
    else:
        result = await run_suite(
            baseline_ids=baselines,
            questions_path=questions_path,
            output_dir=output_dir,
            k=k,
            repo_id_override=repo_id_override,
            corpus_revision=corpus_revision,
        )

    ending_revision = await _read_corpus_revision(repo_id_override)
    if ending_revision != corpus_revision:
        raise RuntimeError(
            "repository corpus changed during evaluation: "
            f"started at revision {corpus_revision}, ended at {ending_revision}"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dcode-eval", description="Dcode evaluation harness")
    parser.add_argument(
        "--baseline",
        required=True,
        nargs="+",
        choices=["B0", "B1", "B2", "B3", "B3.5", "B4"],
        help=(
            "One or more baseline tiers to run. B3.5 is the diagnostic no-graph "
            "arm; it is recorded beside the H1 decision, never inside it"
        ),
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
    parser.add_argument(
        "--repo-id",
        default=None,
        help=(
            "Override the fixture repo_id and resolve gt_targets against this current index repo id"
        ),
    )
    args = parser.parse_args(argv)

    baselines: list[str] = args.baseline
    result = asyncio.run(
        _run_cli(
            baselines=baselines,
            questions_path=args.questions,
            output_dir=args.output,
            k=args.k,
            repo_id_override=args.repo_id,
        )
    )
    if len(baselines) == 1:
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

    print(json.dumps(result["summary"], ensure_ascii=False))
    if result["h1_report"] is not None:
        print(json.dumps(result["h1_report"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
