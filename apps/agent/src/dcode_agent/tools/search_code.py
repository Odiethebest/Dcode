"""Tool: `search_code(query, k)` → List[Chunk].

Calls the hybrid retrieval API: dense plus Okapi BM25, weighted RRF with
`k=60`, and optional cross-encoder reranking.
"""

from dcode_shared.schemas import Chunk
from pydantic import BaseModel, Field

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class SearchCodeArgs(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(10, ge=1, le=50)


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
            {"query": args.query, "k": args.k},
        )
        return SearchCodeResult(chunks=[Chunk.model_validate(item) for item in payload])
