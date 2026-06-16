"""Baseline B1 — standalone BM25 sparse retrieval."""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class BM25Baseline(Baseline):
    id = "B1"
    description = "BM25 over the chunk corpus (DESIGN.md §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # Current API search degrades to sparse-only under the stub embedding model,
        # which is sufficient for the first eval ladder pass.
        return await common.internal_search(repo_id, query, k)

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        chunks = await self.retrieve(repo_id, query, 5)
        return common.template_answer("B1 sparse baseline", chunks)
