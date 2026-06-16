"""Tool: `grep(pattern)` → List[Location].

Implements DESIGN.md §2.3.2 row 7. Backed by ripgrep against the cloned
repo workdir — cheap, precise, and complementary to semantic search.
"""

import asyncio
import json
import re
import shutil
from pathlib import Path

from dcode_shared.schemas import Location
from pydantic import BaseModel

from dcode_agent.tools import common
from dcode_agent.tools.base import Tool

_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__"}


class GrepArgs(BaseModel):
    pattern: str


class GrepResult(BaseModel):
    locations: list[Location]


class GrepTool(Tool[GrepArgs, GrepResult]):
    name = "grep"
    description = "Exact pattern search via ripgrep — cheap and precise."
    ArgsSchema = GrepArgs

    async def execute(self, repo_id: str, args: GrepArgs) -> GrepResult:
        root = common.repo_root(repo_id)
        if shutil.which("rg"):
            locations = await _grep_with_ripgrep(root, args.pattern)
        else:
            locations = _grep_with_python(root, args.pattern)
        return GrepResult(locations=locations)


async def _grep_with_ripgrep(root: Path, pattern: str) -> list[Location]:
    process = await asyncio.create_subprocess_exec(
        "rg",
        "--json",
        "-n",
        "-e",
        pattern,
        str(root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode not in (0, 1):
        error = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"rg failed: {error or process.returncode}")

    matches: list[Location] = []
    for line in stdout.decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") != "match":
            continue
        data = event["data"]
        path = Path(data["path"]["text"]).relative_to(root).as_posix()
        line_number = int(data["line_number"])
        matches.append(
            Location(
                symbol=path,
                file_path=path,
                line=line_number,
                chunk_id=None,
            )
        )
    return matches


def _grep_with_python(root: Path, pattern: str) -> list[Location]:
    regex = re.compile(pattern)
    matches: list[Location] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(lines, start=1):
            if regex.search(line):
                matches.append(
                    Location(
                        symbol=relative,
                        file_path=relative,
                        line=line_number,
                        chunk_id=None,
                    )
                )
    return matches
