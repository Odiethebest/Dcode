"""Baseline B3 — hybrid RAG (dense + sparse + RRF + cross-encoder rerank).

Structural pipeline:
  1. Sparse BM25 candidates (mode=sparse path, large k)
  2. Dense vector candidates (mode=dense path, large k)  — no-op under stub embeddings
  3. RRF fusion of both ranked lists
  4. Identity rerank placeholder  — swap in a real cross-encoder when available

Under stub embeddings B3 produces the same results as B1 because the dense
path returns no candidates. Metrics diverge once a real embedding model is wired
into the API (_embed_search_query in routes/internal.py).
"""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class HybridRAGBaseline(Baseline):
    id = "B3"
    description = "Dense + sparse + RRF + rerank (DESIGN.md §2.2.1 → §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        return await common.internal_search(repo_id, query, k, mode="hybrid")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        chunks = await self.retrieve(repo_id, query, 5)
        return common.template_answer("B3 hybrid baseline", chunks)
