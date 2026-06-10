"""Tool: `search_code(query, k)` → List[Chunk].

Implements DESIGN.md §2.3.2 row 1. Underlying call: hybrid retrieval API
per §2.2.1 (dense + sparse + RRF k=60 + cross-encoder rerank).
"""

from dcode_shared.schemas import Chunk
from pydantic import BaseModel, Field

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
        # TODO(M2): call retrieval API per DESIGN.md §4.2 search(repo_id, query, k).
        raise NotImplementedError("search_code — implement per DESIGN.md §2.3.2 at M2")
