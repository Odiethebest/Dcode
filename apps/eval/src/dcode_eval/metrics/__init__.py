"""Evaluation metrics — DESIGN.md §2.4.4.

Three layers:
  - retrieval.py     — Recall@k / MRR / nDCG (real math, M3-ready)
  - judge.py         — LLM-as-Judge abstract (OD-4 placeholder)
  - groundedness.py  — programmatic citation verification (D-2.3.1)
"""

from dcode_eval.metrics.retrieval import mrr, ndcg_at_k, recall_at_k

__all__ = ["mrr", "ndcg_at_k", "recall_at_k"]
