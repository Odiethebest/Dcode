"""Dcode Evaluation Harness — implements DESIGN.md §2.4.

Runs the five-tier baseline ladder (B0..B4) over a curated question set,
reporting retrieval metrics (Recall@k / MRR / nDCG), answer-quality metrics
(LLM-as-Judge + pairwise win-rate), and groundedness scores.
"""

__version__ = "0.0.0"
