"""Baseline B2 — vanilla dense RAG (single-path vector retrieval + generator)."""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class VanillaRAGBaseline(Baseline):
    id = "B2"
    description = "Single-path dense retrieval + synthesized answer."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # Requests mode=dense; degrades to sparse under stub embeddings until a
        # real embedding model is wired in.
        return await common.internal_search(repo_id, query, k, mode="dense")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        return await common.stream_dense_rag_answer(repo_id, query)
