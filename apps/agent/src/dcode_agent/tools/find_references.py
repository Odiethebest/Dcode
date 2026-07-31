"""Tool: `find_references(symbol)` → List[Location].

Runs the reverse-edge graph query for indexed references to a symbol.
"""

from dcode_shared.schemas import Location
from pydantic import BaseModel

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class FindReferencesArgs(BaseModel):
    symbol: str


class FindReferencesResult(BaseModel):
    locations: list[Location]


class FindReferencesTool(Tool[FindReferencesArgs, FindReferencesResult]):
    name = "find_references"
    description = "Find every callsite that references a symbol (reverse edges)."
    ArgsSchema = FindReferencesArgs

    async def execute(
        self, repo_id: str, args: FindReferencesArgs
    ) -> FindReferencesResult:
        payload = await common.fetch_internal_json(
            "find_references",
            repo_id,
            {"symbol": args.symbol},
        )
        return FindReferencesResult(locations=[Location.model_validate(item) for item in payload])
