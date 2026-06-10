"""Tool: `read_file(path, line_range)` → file slice.

Implements DESIGN.md §2.3.2 row 2. Reads a specific line range from a
file the indexer has already cloned — never opens external files.
"""

from pydantic import BaseModel, Field

from dcode_agent.tools.base import Tool


class ReadFileArgs(BaseModel):
    path: str = Field(..., description="Repo-relative path")
    line_range: tuple[int, int] = Field(..., description="Inclusive [start, end] line numbers")


class ReadFileResult(BaseModel):
    path: str
    line_range: tuple[int, int]
    content: str


class ReadFileTool(Tool[ReadFileArgs, ReadFileResult]):
    name = "read_file"
    description = "Read a specific line range from an indexed file."
    ArgsSchema = ReadFileArgs

    async def execute(self, repo_id: str, args: ReadFileArgs) -> ReadFileResult:
        # TODO(M2): resolve repo workdir for repo_id; read path[line_range].
        raise NotImplementedError("read_file — implement per DESIGN.md §2.3.2 at M2")
