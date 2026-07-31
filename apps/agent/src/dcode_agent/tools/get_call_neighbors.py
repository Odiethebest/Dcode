"""Tool: ``get_call_neighbors(symbol, direction)`` → resolved call edges.

Unlike ``find_references`` (which includes non-call references and only walks
incoming edges), this tool keeps callers and callees separate so synthesis
cannot accidentally invert their meaning.
"""

from dcode_shared.schemas import CallDirection, CallNeighbors
from pydantic import BaseModel, Field

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class GetCallNeighborsArgs(BaseModel):
    symbol: str = Field(..., min_length=1)
    direction: CallDirection = "both"


class GetCallNeighborsTool(Tool[GetCallNeighborsArgs, CallNeighbors]):
    name = "get_call_neighbors"
    description = (
        "Find resolved callers, callees, or both for a function/method. "
        "The result keeps call direction explicit."
    )
    ArgsSchema = GetCallNeighborsArgs

    async def execute(self, repo_id: str, args: GetCallNeighborsArgs) -> CallNeighbors:
        payload = await common.fetch_internal_json(
            "get_call_neighbors",
            repo_id,
            {"symbol": args.symbol, "direction": args.direction},
        )
        return CallNeighbors.model_validate(payload)
