"""Baseline B3 — hybrid RAG (dense + sparse + RRF + cross-encoder rerank)."""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class HybridRAGBaseline(Baseline):
    id = "B3"
    description = "Dense + sparse + RRF + rerank (DESIGN.md §2.2.1 → §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        return await common.internal_search(repo_id, query, k)

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        chunks = await self.retrieve(repo_id, query, 5)
        return common.template_answer("B3 hybrid baseline", chunks)
