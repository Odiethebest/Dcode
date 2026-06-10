"""Baseline B1 — standalone BM25 sparse retrieval."""

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_shared.schemas import Chunk


class BM25Baseline(Baseline):
    id = "B1"
    description = "BM25 over the chunk corpus (DESIGN.md §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # TODO(M3): run BM25 over chunks.tsv per DESIGN.md §3.2 indexes.
        raise NotImplementedError("B1 retrieve — implement per DESIGN.md §2.4.3 at M3")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        raise NotImplementedError("B1 answer — implement per DESIGN.md §2.4.3 at M3")
