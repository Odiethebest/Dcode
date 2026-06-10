"""Baseline B3 — hybrid RAG (dense + sparse + RRF + cross-encoder rerank)."""

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_shared.schemas import Chunk


class HybridRAGBaseline(Baseline):
    id = "B3"
    description = "Dense + sparse + RRF + rerank (DESIGN.md §2.2.1 → §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # TODO(M3): same retrieval as the full system MINUS the agent loop /
        # graph queries. Calls the retrieval API directly.
        raise NotImplementedError("B3 retrieve — implement per DESIGN.md §2.4.3 at M3")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        # TODO(M3): retrieve top-k via hybrid → single LLM call (no tool loop).
        raise NotImplementedError("B3 answer — implement per DESIGN.md §2.4.3 at M3")
