"""Retrieval metrics — DESIGN.md §2.4.4 (Recall@k / MRR / nDCG).

Real implementations (not stubs) — these are pure math, no LLM, and they
are exercised by the harness on every eval run starting at M3.
"""

import math
from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], gt: set[str], k: int) -> float:
    """Recall@k: fraction of GT chunk-ids present in the first k retrieved.

    Returns 1.0 when GT is empty (vacuously satisfied).
    """
    if not gt:
        return 1.0
    hits = sum(1 for cid in retrieved[:k] if cid in gt)
    return hits / len(gt)


def mrr(retrieved: Sequence[str], gt: set[str]) -> float:
    """Mean Reciprocal Rank: 1 / rank of the first GT hit (0 if none)."""
    for i, cid in enumerate(retrieved, start=1):
        if cid in gt:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], gt: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain @ k with binary relevance."""
    dcg = sum(
        1.0 / math.log2(i + 2)
        for i, cid in enumerate(retrieved[:k])
        if cid in gt
    )
    ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(gt), k)))
    return dcg / ideal_dcg if ideal_dcg > 0 else 0.0
