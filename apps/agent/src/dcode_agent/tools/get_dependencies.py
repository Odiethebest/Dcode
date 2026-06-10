"""Tool: `get_dependencies(module)` → List[Module].

Implements DESIGN.md §2.3.2 row 5. Module-level import-edge query.
"""

from pydantic import BaseModel

from dcode_agent.tools.base import Tool


class GetDependenciesArgs(BaseModel):
    module: str


class GetDependenciesResult(BaseModel):
    modules: list[str]


class GetDependenciesTool(Tool[GetDependenciesArgs, GetDependenciesResult]):
    name = "get_dependencies"
    description = "List the modules that a given module imports."
    ArgsSchema = GetDependenciesArgs

    async def execute(
        self, repo_id: str, args: GetDependenciesArgs
    ) -> GetDependenciesResult:
        # TODO(M2): query edges WHERE source = module symbol AND edge_type = 'imports'.
        raise NotImplementedError("get_dependencies — implement per DESIGN.md §2.3.2 at M2")
