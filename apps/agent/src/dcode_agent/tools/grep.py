"""Tool: `grep(pattern)` → List[Location].

Implements DESIGN.md §2.3.2 row 7. Backed by ripgrep against the cloned
repo workdir — cheap, precise, and complementary to semantic search.
"""

from dcode_shared.schemas import Location
from pydantic import BaseModel

from dcode_agent.tools.base import Tool


class GrepArgs(BaseModel):
    pattern: str


class GrepResult(BaseModel):
    locations: list[Location]


class GrepTool(Tool[GrepArgs, GrepResult]):
    name = "grep"
    description = "Exact pattern search via ripgrep — cheap and precise."
    ArgsSchema = GrepArgs

    async def execute(self, repo_id: str, args: GrepArgs) -> GrepResult:
        # TODO(M2): subprocess `rg --json -n <pattern> <workdir>`; parse to Locations.
        raise NotImplementedError("grep — implement per DESIGN.md §2.3.2 at M2")
