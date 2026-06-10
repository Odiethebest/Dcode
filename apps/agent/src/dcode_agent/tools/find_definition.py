"""Tool: `find_definition(symbol)` → List[Location].

Implements DESIGN.md §2.3.2 row 3. Backed by the code-graph query API
(§2.2.2): look up symbol definition location(s).
"""

from pydantic import BaseModel

from dcode_agent.tools.base import Tool
from dcode_shared.schemas import Location


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
        # TODO(M2): call graph API per DESIGN.md §4.2 with (repo_id, symbol).
        raise NotImplementedError("find_definition — implement per DESIGN.md §2.3.2 at M2")
