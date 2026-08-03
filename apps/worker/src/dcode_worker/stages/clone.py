"""Pipeline stage: shallow-clone the target Git repository."""

import asyncio
import os
import shutil
from pathlib import Path
from uuid import UUID

from dcode_worker.context import PipelineContext
from dcode_worker.settings import worker_settings
from dcode_worker.stages import prune

CLONE_TIMEOUT_SECONDS = 180


async def run(ctx: PipelineContext) -> PipelineContext:
    """Clone `ctx.repo_url` into an isolated workdir and record HEAD SHA."""
    repo_uuid = UUID(ctx.repo_id)
    workdir = Path(worker_settings.workdir_base).expanduser().resolve() / str(repo_uuid)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    # Reclaim space before needing it. Off unless WORKDIR_MAX_REPOS is set.
    prune.prune_workdirs(
        workdir.parent,
        keep=worker_settings.workdir_max_repos,
        protect=str(repo_uuid),
    )
    if workdir.exists():
        shutil.rmtree(workdir)

    # `--` before the URL. Without it git parses a value beginning with "-" as
    # an option, and `--upload-pack=<cmd>` is command execution. The gateway
    # validates the URL, but the worker consumes a queue message and should not
    # depend on the only check being upstream of it.
    await _run_git("clone", "--depth=1", "--", ctx.repo_url, str(workdir), cwd=None)
    commit_sha = await _run_git("rev-parse", "HEAD", cwd=workdir)

    ctx.workdir = str(workdir)
    ctx.commit_sha = commit_sha.strip()
    return ctx


# git will sit waiting for a username on a private or mistyped repository, and
# with no terminal it inherits one from the container's environment or hangs
# until the clone timeout. Fail immediately instead: "authentication required"
# is a better answer after two seconds than after three minutes.
_GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "",
    "GCM_INTERACTIVE": "never",
}


async def _run_git(*args: str, cwd: Path | None) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd) if cwd is not None else None,
        env={**os.environ, **_GIT_ENV},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), CLONE_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError(f"git {' '.join(args)} timed out") from exc

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")
    if process.returncode != 0:
        detail = stderr_text.strip() or stdout_text.strip() or f"exit code {process.returncode}"
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return stdout_text
