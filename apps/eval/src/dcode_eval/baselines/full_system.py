"""Baseline B4 — the full Dcode system (hybrid + call graph + agent)."""

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_shared.schemas import Chunk


class FullSystemBaseline(Baseline):
    id = "B4"
    description = "Dcode — hybrid retrieval + call graph + ReAct agent (DESIGN.md §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # TODO(M3): call retrieval API directly so retrieval-only metrics
        # are comparable to B2 / B3 (skip the agent loop).
        raise NotImplementedError("B4 retrieve — implement per DESIGN.md §2.4.3 at M3")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        # TODO(M3): POST to agent /internal/query, drain SSE, assemble AnswerResult
        # with final_answer text + verified citations + groundedness.
        raise NotImplementedError("B4 answer — implement per DESIGN.md §2.4.3 at M3")
