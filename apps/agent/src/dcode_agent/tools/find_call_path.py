"""Tool: `find_call_path(start, end, max_depth)` → CallPath.

Architecture questions ask how control reaches B from A. The existing graph
tools answer a different question: `find_references` lists every reference to
one symbol, and `get_call_neighbors` lists one symbol's immediate neighbours.
Both flood the context with locations that are not on the path being asked
about, which measurably cost the full arm on architecture questions.

An empty path is a real answer and is reported as one. The graph has documented
blind spots — no type inference, unresolved inherited `self.method()` — so
"no static chain within max_depth" is common and must not be presented as
"these two are unrelated".
"""

from dcode_shared.schemas import CallPath
from pydantic import BaseModel, Field

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class FindCallPathArgs(BaseModel):
    start: str = Field(..., min_length=1)
    end: str = Field(..., min_length=1)
    max_depth: int = Field(4, ge=1, le=6)


class FindCallPathTool(Tool[FindCallPathArgs, CallPath]):
    name = "find_call_path"
    description = (
        "Find the shortest chain of call edges between two symbols. "
        "Use for 'how does X reach Y' or end-to-end flow questions."
    )
    ArgsSchema = FindCallPathArgs

    async def execute(self, repo_id: str, args: FindCallPathArgs) -> CallPath:
        payload = await common.fetch_internal_json(
            "find_call_path",
            repo_id,
            {"start": args.start, "end": args.end, "max_depth": args.max_depth},
        )
        return CallPath.model_validate(payload)
