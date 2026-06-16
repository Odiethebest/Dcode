"""Baseline ladder — DESIGN.md §2.4.3 B0..B4.

Each baseline subclasses `Baseline` and exposes `retrieve()` (for IR metrics)
and `answer()` (for judge + groundedness). The harness selects one per run
based on the `--baseline` CLI argument.
"""

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.baselines.bm25 import BM25Baseline
from dcode_eval.baselines.full_system import FullSystemBaseline
from dcode_eval.baselines.github_search import GithubSearchBaseline
from dcode_eval.baselines.hybrid_rag import HybridRAGBaseline
from dcode_eval.baselines.vanilla_rag import VanillaRAGBaseline

__all__ = [
    "AnswerResult",
    "BM25Baseline",
    "Baseline",
    "FullSystemBaseline",
    "GithubSearchBaseline",
    "HybridRAGBaseline",
    "VanillaRAGBaseline",
]


def build_baseline(baseline_id: str) -> Baseline:
    catalog: dict[str, type[Baseline]] = {
        "B0": GithubSearchBaseline,
        "B1": BM25Baseline,
        "B2": VanillaRAGBaseline,
        "B3": HybridRAGBaseline,
        "B4": FullSystemBaseline,
    }
    try:
        return catalog[baseline_id]()
    except KeyError as exc:
        raise ValueError(f"unknown baseline: {baseline_id}") from exc
