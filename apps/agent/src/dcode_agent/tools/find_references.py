"""Tool: `find_references(symbol)` → List[Location].

Implements DESIGN.md §2.3.2 row 4. Reverse-edge query on the code graph
(§2.2.2): "who calls / references this symbol?".
"""

from pydantic import BaseModel

from dcode_agent.tools.base import Tool
from dcode_shared.schemas import Location


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
        # TODO(M2): query edges WHERE target_id = symbols.id AND edge_type IN ('calls', 'references').
        raise NotImplementedError("find_references — implement per DESIGN.md §2.3.2 at M2")
