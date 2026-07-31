"""Canonical evaluation baseline ladder B0 through B4.

Each baseline subclasses `Baseline` and exposes `retrieve()` (for IR metrics)
and `answer()` (for judge + groundedness). The harness selects one per run
based on the `--baseline` CLI argument.
"""

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.baselines.bm25 import BM25Baseline
from dcode_eval.baselines.full_system import FullSystemBaseline
from dcode_eval.baselines.github_search import GithubSearchBaseline
from dcode_eval.baselines.hybrid_agent_no_graph import HybridAgentNoGraphBaseline
from dcode_eval.baselines.hybrid_rag import HybridRAGBaseline
from dcode_eval.baselines.vanilla_rag import VanillaRAGBaseline

__all__ = [
    "AnswerResult",
    "BM25Baseline",
    "Baseline",
    "FullSystemBaseline",
    "GithubSearchBaseline",
    "HybridAgentNoGraphBaseline",
    "HybridRAGBaseline",
    "VanillaRAGBaseline",
]

# Arms that answer through the shared agent path, and can therefore be scored on
# their verified final evidence. B0/B1 are retrieval references that answer from
# a template; they emit no citations, so the official rule cannot apply to them
# and they are excluded from the H1 decision.
AGENT_BASELINES = frozenset({"B2", "B3", "B3.5", "B4"})

# The H1 decision compares B4 against these. B3.5 is deliberately absent:
# it is a diagnostic, and adding an arm to the decision rule would be changing
# the pass criteria.
DECISION_BASELINES = ("B2", "B3", "B4")


def build_baseline(baseline_id: str) -> Baseline:
    catalog: dict[str, type[Baseline]] = {
        "B0": GithubSearchBaseline,
        "B1": BM25Baseline,
        "B2": VanillaRAGBaseline,
        "B3": HybridRAGBaseline,
        "B3.5": HybridAgentNoGraphBaseline,
        "B4": FullSystemBaseline,
    }
    try:
        return catalog[baseline_id]()
    except KeyError as exc:
        raise ValueError(f"unknown baseline: {baseline_id}") from exc
