"""Baseline B2 — vanilla dense RAG (single-path vector retrieval + generator)."""

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_shared.schemas import Chunk


class VanillaRAGBaseline(Baseline):
    id = "B2"
    description = "Single-path dense retrieval + LLM answer (DESIGN.md §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # TODO(M3): pgvector cosine search over chunks.embedding (no rerank, no sparse).
        raise NotImplementedError("B2 retrieve — implement per DESIGN.md §2.4.3 at M3")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        # TODO(M3): retrieve top-k → stuff into a single prompt → LLM answer.
        raise NotImplementedError("B2 answer — implement per DESIGN.md §2.4.3 at M3")
