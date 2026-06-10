"""Baseline B0 — GitHub Search (pure keyword).

Industry-standard control: queries the public GitHub code search API.
"""

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_shared.schemas import Chunk


class GithubSearchBaseline(Baseline):
    id = "B0"
    description = "GitHub code search — pure keyword (DESIGN.md §2.4.3)."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # TODO(M3): GET https://api.github.com/search/code with q="<query> repo:<owner/name>"
        raise NotImplementedError("B0 retrieve — implement per DESIGN.md §2.4.3 at M3")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        # TODO(M3): B0 has no LLM — answer is the top-k snippets joined verbatim.
        raise NotImplementedError("B0 answer — implement per DESIGN.md §2.4.3 at M3")
