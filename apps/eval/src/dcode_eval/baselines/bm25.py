"""Baseline B1 — standalone BM25 sparse retrieval."""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class BM25Baseline(Baseline):
    id = "B1"
    description = "Okapi BM25 over the complete chunk corpus."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        return await common.internal_search(repo_id, query, k, mode="sparse")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        chunks = await self.retrieve(repo_id, query, 5)
        return common.template_answer("B1 sparse baseline", chunks)
