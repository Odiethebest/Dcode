"""Tool: `get_dependents(module)` → List[Location].

Reverse of `get_dependencies`: the modules that import the given module
(incoming import edges, backed by the ix_edges_target reverse index).
"""

from dcode_shared.schemas import Location
from pydantic import BaseModel

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class GetDependentsArgs(BaseModel):
    module: str


class GetDependentsResult(BaseModel):
    locations: list[Location]


class GetDependentsTool(Tool[GetDependentsArgs, GetDependentsResult]):
    name = "get_dependents"
    description = "List the modules that import a given module (reverse dependencies)."
    ArgsSchema = GetDependentsArgs

    async def execute(self, repo_id: str, args: GetDependentsArgs) -> GetDependentsResult:
        payload = await common.fetch_internal_json(
            "get_dependents",
            repo_id,
            {"module": args.module},
        )
        return GetDependentsResult(locations=[Location.model_validate(item) for item in payload])
