"""Tool: `find_references(symbol)` → List[Location].

Implements DESIGN.md §2.3.2 row 4. Reverse-edge query on the code graph
(§2.2.2): "who calls / references this symbol?".
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
