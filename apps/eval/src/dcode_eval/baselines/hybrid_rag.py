"""Baseline B3 — hybrid RAG (dense + sparse + weighted RRF + cross-encoder rerank).

Structural pipeline:
  1. Sparse BM25 candidates (mode=sparse path, large k)
  2. Dense vector candidates (mode=dense path, large k)
  3. Weighted RRF fusion (default dense_weight=2, sparse_weight=1)
  4. Cross-encoder rerank when RERANKER_MODEL is not stub

Requires real embeddings for dense candidates and a real reranker for B3 to
beat dense-only (B2). Under stub embeddings/reranker, B3 collapses toward
sparse or fused-score order.
"""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class HybridRAGBaseline(Baseline):
    id = "B3"
    description = "Dense + Okapi BM25 + weighted RRF + rerank."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        return await common.internal_search(repo_id, query, k, mode="hybrid")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        return await common.stream_hybrid_rag_answer(repo_id, query)
