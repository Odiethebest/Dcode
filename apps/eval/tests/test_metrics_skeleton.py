"""Eval harness smoke tests — baseline ladder + retrieval metric math."""

import pytest
from dcode_eval.baselines import (
    BM25Baseline,
    FullSystemBaseline,
    GithubSearchBaseline,
    HybridRAGBaseline,
    VanillaRAGBaseline,
)
from dcode_eval.metrics.retrieval import mrr, ndcg_at_k, recall_at_k


def test_baseline_ladder_has_five_systems() -> None:
    """DESIGN.md §2.4.3 enumerates exactly B0..B4."""
    baselines = (
        GithubSearchBaseline(),
        BM25Baseline(),
        VanillaRAGBaseline(),
        HybridRAGBaseline(),
        FullSystemBaseline(),
    )
    assert {b.id for b in baselines} == {"B0", "B1", "B2", "B3", "B4"}


def test_recall_at_k_full_match() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, k=3) == pytest.approx(1.0)


def test_recall_at_k_partial_match() -> None:
    assert recall_at_k(["x", "a", "z"], {"a", "b"}, k=3) == pytest.approx(0.5)


def test_recall_at_k_vacuous_when_no_gt() -> None:
    assert recall_at_k(["a", "b"], set(), k=3) == 1.0


def test_mrr_first_hit_is_one() -> None:
    assert mrr(["a", "b", "c"], {"a"}) == pytest.approx(1.0)


def test_mrr_third_hit_is_one_third() -> None:
    assert mrr(["x", "y", "z"], {"z"}) == pytest.approx(1 / 3)


def test_mrr_no_hit_is_zero() -> None:
    assert mrr(["x", "y"], {"z"}) == 0.0


def test_ndcg_perfect_when_top_k_is_gt() -> None:
    assert ndcg_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == pytest.approx(1.0)


def test_ndcg_zero_when_no_overlap() -> None:
    assert ndcg_at_k(["x", "y", "z"], {"a"}, k=3) == 0.0
