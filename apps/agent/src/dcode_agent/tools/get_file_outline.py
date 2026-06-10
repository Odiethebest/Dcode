"""Tool: `get_file_outline(path)` → List[Symbol].

Implements DESIGN.md §2.3.2 row 6. List the symbols (classes / functions)
defined in a single file.
"""

from pydantic import BaseModel

from dcode_agent.tools.base import Tool


class GetFileOutlineArgs(BaseModel):
    path: str


class OutlineEntry(BaseModel):
    symbol: str
    kind: str  # function / class / method
    line: int


class GetFileOutlineResult(BaseModel):
    path: str
    entries: list[OutlineEntry]


class GetFileOutlineTool(Tool[GetFileOutlineArgs, GetFileOutlineResult]):
    name = "get_file_outline"
    description = "List the classes and functions defined in a file."
    ArgsSchema = GetFileOutlineArgs

    async def execute(
        self, repo_id: str, args: GetFileOutlineArgs
    ) -> GetFileOutlineResult:
        # TODO(M2): SELECT symbols WHERE repo_id, file_path ORDER BY line.
        raise NotImplementedError("get_file_outline — implement per DESIGN.md §2.3.2 at M2")
