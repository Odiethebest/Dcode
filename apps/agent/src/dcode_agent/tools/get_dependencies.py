"""Tool: `get_dependencies(module)` → List[Location].

Implements DESIGN.md §2.3.2 row 5. Module-level import-edge query.
"""

from dcode_shared.schemas import Location
from pydantic import BaseModel

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class GetDependenciesArgs(BaseModel):
    module: str


class GetDependenciesResult(BaseModel):
    locations: list[Location]


class GetDependenciesTool(Tool[GetDependenciesArgs, GetDependenciesResult]):
    name = "get_dependencies"
    description = "List the modules that a given module imports."
    ArgsSchema = GetDependenciesArgs

    async def execute(
        self, repo_id: str, args: GetDependenciesArgs
    ) -> GetDependenciesResult:
        payload = await common.fetch_internal_json(
            "get_dependencies",
            repo_id,
            {"module": args.module},
        )
        return GetDependenciesResult(locations=[Location.model_validate(item) for item in payload])
