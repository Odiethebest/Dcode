"""Pipeline stage: shallow-clone the target Git repository."""

import asyncio
import shutil
from pathlib import Path
from uuid import UUID

from dcode_worker.context import PipelineContext
from dcode_worker.settings import worker_settings

CLONE_TIMEOUT_SECONDS = 180


async def run(ctx: PipelineContext) -> PipelineContext:
    """Clone `ctx.repo_url` into an isolated workdir and record HEAD SHA."""
    repo_uuid = UUID(ctx.repo_id)
    workdir = Path(worker_settings.workdir_base).expanduser().resolve() / str(repo_uuid)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    if workdir.exists():
        shutil.rmtree(workdir)

    await _run_git("clone", "--depth=1", ctx.repo_url, str(workdir), cwd=None)
    commit_sha = await _run_git("rev-parse", "HEAD", cwd=workdir)

    ctx.workdir = str(workdir)
    ctx.commit_sha = commit_sha.strip()
    return ctx


async def _run_git(*args: str, cwd: Path | None) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd) if cwd is not None else None,
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
