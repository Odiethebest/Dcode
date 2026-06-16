"""Tool: `read_file(path, line_range)` → file slice.

Implements DESIGN.md §2.3.2 row 2. Reads a specific line range from a
file the indexer has already cloned — never opens external files.
"""

from pydantic import BaseModel, Field, model_validator

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool


class ReadFileArgs(BaseModel):
    path: str = Field(..., description="Repo-relative path")
    line_range: tuple[int, int] = Field(..., description="Inclusive [start, end] line numbers")

    @model_validator(mode="after")
    def validate_line_range(self) -> "ReadFileArgs":
        start, end = self.line_range
        if start < 1 or end < 1:
            raise ValueError("line_range must be positive and 1-based")
        if start > end:
            raise ValueError("line_range start must be <= end")
        return self


class ReadFileResult(BaseModel):
    path: str
    line_range: tuple[int, int]
    content: str


class ReadFileTool(Tool[ReadFileArgs, ReadFileResult]):
    name = "read_file"
    description = "Read a specific line range from an indexed file."
    ArgsSchema = ReadFileArgs

    async def execute(self, repo_id: str, args: ReadFileArgs) -> ReadFileResult:
        target = common.resolve_repo_path(repo_id, args.path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"file not found: {args.path}")

        lines = target.read_text(encoding="utf-8").splitlines()
        start, end = args.line_range
        content = "\n".join(lines[start - 1 : end])
        return ReadFileResult(
            path=common.repo_relative_path(repo_id, target),
            line_range=args.line_range,
            content=content,
        )
