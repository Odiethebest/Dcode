"""Baseline B2 — vanilla dense RAG (single-path vector retrieval + generator)."""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class VanillaRAGBaseline(Baseline):
    id = "B2"
    description = "Single-path dense retrieval + LLM answer (DESIGN.md §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # The current index still uses stub embeddings, so this dense baseline
        # temporarily reuses the retrieval API until real query embeddings land.
        return await common.internal_search(repo_id, query, k)

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        chunks = await self.retrieve(repo_id, query, 5)
        return common.template_answer("B2 dense baseline", chunks)
