"""Tool: `search_code(query, k, mode)` → List[Chunk].

Defaults to the hybrid retrieval API: dense plus Okapi BM25, weighted RRF with
`k=60`, and optional cross-encoder reranking. `mode` exists so an evaluation arm
can hold the rest of the agent fixed and vary only retrieval — `dense` is what
makes B2 a vanilla-RAG arm running the real synthesis and guardrail path.

`mode` is a tool argument rather than ambient state on purpose: the tool cache
key is derived from `(tool, repo_id, args)`, so a retrieval mode carried outside
the args would let a dense search and a hybrid search for the same query share
one cache entry.
"""

from typing import Literal

from dcode_shared.schemas import Chunk
from pydantic import BaseModel, Field

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class SearchCodeArgs(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(10, ge=1, le=50)
    mode: Literal["hybrid", "dense", "sparse"] = "hybrid"


class SearchCodeResult(BaseModel):
    chunks: list[Chunk]


class SearchCodeTool(Tool[SearchCodeArgs, SearchCodeResult]):
    name = "search_code"
    description = (
        "Hybrid semantic + lexical search over indexed code chunks. "
        "Use when looking up code by natural-language intent."
    )
    ArgsSchema = SearchCodeArgs

    async def execute(self, repo_id: str, args: SearchCodeArgs) -> SearchCodeResult:
        payload = await common.fetch_internal_json(
            "search",
            repo_id,
            {"query": args.query, "k": args.k, "mode": args.mode},
        )
        return SearchCodeResult(chunks=[Chunk.model_validate(item) for item in payload])
