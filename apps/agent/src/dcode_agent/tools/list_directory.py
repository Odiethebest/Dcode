"""Tool: `list_directory(path)` → List[FileEntry].

Implements DESIGN.md §2.3.2 row 8. Filesystem listing of the cloned
repo workdir — for repo-tree navigation.
"""

from pathlib import Path

from pydantic import BaseModel

from dcode_agent.tools import common
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
        target = common.resolve_repo_path(repo_id, args.path)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"directory not found: {args.path}")

        entries: list[FileEntry] = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name)):
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            kind = "dir" if child.is_dir() else "file"
            relative = _entry_name(target, child)
            entries.append(FileEntry(name=relative, kind=kind))
        return ListDirectoryResult(entries=entries)


def _entry_name(parent: Path, child: Path) -> str:
    return child.relative_to(parent).as_posix()
