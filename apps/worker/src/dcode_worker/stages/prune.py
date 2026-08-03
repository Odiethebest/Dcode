"""Bound the workdir volume by evicting the least recently used checkouts.

Runs before a clone, so the space is reclaimed before it is needed rather than
after a disk-full failure.

Read `WORKDIR_MAX_REPOS` in `dcode_worker.settings` before changing anything
here: eviction is a real trade, not a cleanup. The agent's file tools read these
trees at query time, so an evicted repository keeps working for search and the
call graph and loses `read_file`, `grep` and `list_directory` until it is
re-indexed.
"""

import logging
import shutil
from pathlib import Path

from dcode_shared.observability import log_event

logger = logging.getLogger("dcode.worker.prune")


def prune_workdirs(base: Path, *, keep: int, protect: str) -> list[str]:
    """Evict oldest-first until at most `keep` workdirs remain. Returns evicted ids.

    `protect` is the repository about to be cloned; evicting it would delete the
    directory the caller is on its way to writing.

    `keep <= 0` disables eviction entirely, which is the default.
    """
    if keep <= 0 or not base.is_dir():
        return []

    candidates = [
        path for path in base.iterdir() if path.is_dir() and path.name != protect
    ]
    # Oldest first. mtime rather than a recorded access time because nothing
    # records access: it is a proxy for "least recently indexed", which is the
    # closest available signal and is stated here rather than implied.
    candidates.sort(key=lambda path: path.stat().st_mtime)

    # `protect` occupies one slot whether or not it exists yet.
    excess = (len(candidates) + 1) - keep
    evicted: list[str] = []
    for path in candidates[: max(0, excess)]:
        try:
            shutil.rmtree(path)
        except OSError as exc:
            # A workdir that will not delete is not a reason to fail the index.
            log_event(logger, "workdir_prune_failed", repo_id=path.name, error=str(exc))
            continue
        evicted.append(path.name)

    if evicted:
        log_event(
            logger,
            "workdir_pruned",
            count=len(evicted),
            keep=keep,
            repo_ids=",".join(evicted),
        )
    return evicted
