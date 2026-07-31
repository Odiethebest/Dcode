"""Tool: `find_definition(symbol)` → List[Location].

Backed by the internal code-graph API for symbol-definition locations.
"""

from dcode_shared.schemas import Location
from pydantic import BaseModel

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class FindDefinitionArgs(BaseModel):
    symbol: str


class FindDefinitionResult(BaseModel):
    locations: list[Location]


class FindDefinitionTool(Tool[FindDefinitionArgs, FindDefinitionResult]):
    name = "find_definition"
    description = "Locate the definition of a symbol (function/class/method)."
    ArgsSchema = FindDefinitionArgs

    async def execute(
        self, repo_id: str, args: FindDefinitionArgs
    ) -> FindDefinitionResult:
        payload = await common.fetch_internal_json(
            "find_definition",
            repo_id,
            {"symbol": args.symbol},
        )
        return FindDefinitionResult(locations=[Location.model_validate(item) for item in payload])
