"""Evaluation metric modules.

Three layers:
  - retrieval.py     — deterministic Recall@k / MRR / nDCG
  - judge.py         — answer-quality interface plus the current stub
  - groundedness.py  — programmatic citation-verification interface
"""

from dcode_eval.metrics.retrieval import mrr, ndcg_at_k, recall_at_k

__all__ = ["mrr", "ndcg_at_k", "recall_at_k"]
