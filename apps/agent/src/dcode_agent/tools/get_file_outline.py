"""Tool: `get_file_outline(path)` → List[Location].

Implements DESIGN.md §2.3.2 row 6. List the symbols (classes / functions)
defined in a single file.
"""

from dcode_shared.schemas import Location
from pydantic import BaseModel, Field

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class GetFileOutlineArgs(BaseModel):
    path: str = Field(..., description="Repo-relative path")


class GetFileOutlineResult(BaseModel):
    path: str
    locations: list[Location]


class GetFileOutlineTool(Tool[GetFileOutlineArgs, GetFileOutlineResult]):
    name = "get_file_outline"
    description = "List the classes and functions defined in a file."
    ArgsSchema = GetFileOutlineArgs

    async def execute(
        self, repo_id: str, args: GetFileOutlineArgs
    ) -> GetFileOutlineResult:
        normalized_path = common.normalize_repo_relative_path(args.path)
        payload = await common.fetch_internal_json(
            "get_file_outline",
            repo_id,
            {"path": normalized_path},
        )
        return GetFileOutlineResult(
            path=normalized_path,
            locations=[Location.model_validate(item) for item in payload],
        )
