"""Dcode evaluation harness and five-tier baseline ladder.

Runs the five-tier baseline ladder (B0..B4) over a curated question set,
reporting retrieval metrics (Recall@k / MRR / nDCG) and groundedness. The judge
interface exists, but the recorded run uses the stub and leaves pairwise
win-rate unmeasured.
"""

__version__ = "0.0.0"
