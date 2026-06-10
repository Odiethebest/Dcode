"""Tool: `list_directory(path)` → List[FileEntry].

Implements DESIGN.md §2.3.2 row 8. Filesystem listing of the cloned
repo workdir — for repo-tree navigation.
"""

from pydantic import BaseModel

from dcode_agent.tools.base import Tool


class ListDirectoryArgs(BaseModel):
    path: str = "."


class FileEntry(BaseModel):
    name: str
    kind: str  # 'file' | 'dir'


class ListDirectoryResult(BaseModel):
    entries: list[FileEntry]


class ListDirectoryTool(Tool[ListDirectoryArgs, ListDirectoryResult]):
    name = "list_directory"
    description = "List entries (files + subdirectories) under a path."
    ArgsSchema = ListDirectoryArgs

    async def execute(
        self, repo_id: str, args: ListDirectoryArgs
    ) -> ListDirectoryResult:
        # TODO(M2): os.scandir(workdir / args.path), filter hidden, classify entries.
        raise NotImplementedError("list_directory — implement per DESIGN.md §2.3.2 at M2")
