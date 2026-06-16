"""Baseline B4 — the full Dcode system (hybrid + call graph + agent)."""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class FullSystemBaseline(Baseline):
    id = "B4"
    description = "Dcode — hybrid retrieval + call graph + ReAct agent (DESIGN.md §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        return await common.internal_search(repo_id, query, k)

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        return await common.stream_full_system_answer(repo_id, query)
