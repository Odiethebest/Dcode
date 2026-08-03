"""Tool: `grep(pattern)` → List[Location].

Backed by ripgrep against the cloned repository workdir — cheap, precise, and
complementary to semantic search.
"""

import asyncio
import json
import re
import shutil
import time
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


# Bounds on a tool whose argument is a user-influenced pattern.
#
# `.` over a large repository produced hundreds of MB of JSON, buffered whole in
# the agent process and then serialised into Redis and the SSE state. None of
# that is useful to an answer: a pattern matching everything has told you
# nothing, and the first few hundred hits are as informative as the first few
# hundred thousand.
_MATCH_LIMIT = 500
_PER_FILE_MATCH_LIMIT = 20
_MAX_FILE_BYTES = 1_000_000
_GREP_TIMEOUT_SECONDS = 20.0


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
        # Bounded at the source rather than after the fact: rg stops looking
        # instead of the agent reading everything and throwing most away.
        f"--max-count={_PER_FILE_MATCH_LIMIT}",
        f"--max-filesize={_MAX_FILE_BYTES}",
        "-e",
        pattern,
        str(root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=_GREP_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        # The clone path has a timeout and this did not, so a pathological
        # pattern had no ceiling at all.
        process.kill()
        await process.wait()
        raise RuntimeError(f"grep timed out after {_GREP_TIMEOUT_SECONDS:.0f}s") from exc
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
        if len(matches) >= _MATCH_LIMIT:
            break
    return matches


def _grep_with_python(root: Path, pattern: str) -> list[Location]:
    """Fallback for when ripgrep is absent. Bounded, but not fully.

    Honest limit: Python has no way to time out a single `re` call, so a pattern
    with catastrophic backtracking against one long line can still block the
    event loop. What is bounded is everything countable — total matches, matches
    per file, file size, and a wall-clock deadline checked between files.

    The agent image installs ripgrep, so this path runs only where it is
    missing: a host-run process or a stripped image. That is why the residual
    risk is recorded rather than solved with a subprocess.
    """
    regex = re.compile(pattern)
    deadline = time.monotonic() + _GREP_TIMEOUT_SECONDS
    matches: list[Location] = []
    for path in sorted(root.rglob("*")):
        if len(matches) >= _MATCH_LIMIT or time.monotonic() > deadline:
            break
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        in_file = 0
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
                in_file += 1
                if in_file >= _PER_FILE_MATCH_LIMIT or len(matches) >= _MATCH_LIMIT:
                    break
    return matches
