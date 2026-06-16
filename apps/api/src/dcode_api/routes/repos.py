"""Indexing endpoints — implements DESIGN.md §4.1."""

import ipaddress
import json
import re
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse
from uuid import UUID

from dcode_shared.cache import job_state_key
from dcode_shared.db.models import Repo
from dcode_shared.schemas import (
    RepoCreateRequest,
    RepoCreateResponse,
    RepoStatus,
    RepoStatusResponse,
    StagesStatus,
    StageState,
)
from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from dcode_api.deps import get_db, get_index_job_publisher, get_redis

router = APIRouter(tags=["repos"])

_SCP_LIKE_GIT_URL = re.compile(r"^[\w.-]+@[\w.-]+:[\w./-]+(?:\.git)?$")
_ALLOWED_URL_SCHEMES = {"https", "http", "ssh", "git"}


@router.post(
    "/repos",
    response_model=RepoCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_repo(
    body: RepoCreateRequest,
    db: AsyncSession = Depends(get_db),
    publish_job: Callable[[UUID, str], Awaitable[None]] = Depends(get_index_job_publisher),
) -> RepoCreateResponse:
    """Submit a repository for indexing.

    Persists a queued Repo row, then publishes the indexing job to RabbitMQ.
    If publishing fails, the row is rolled back and the request fails rather
    than leaving a repo that will never be consumed by the worker.
    """
    repo_url = body.url.strip()
    if not _is_supported_git_url(repo_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_REPO_URL",
                "message": "Expected an http(s), ssh, git, or git@host:path Git URL.",
            },
        )

    repo = Repo(url=repo_url, status=RepoStatus.queued.value, progress=0)
    db.add(repo)
    await db.flush()

    try:
        await publish_job(repo.id, repo_url)
    except Exception as exc:  # noqa: BLE001 — convert infra failures to API errors
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "INDEX_QUEUE_UNAVAILABLE",
                "message": "Repository was not queued because RabbitMQ publish failed.",
            },
        ) from exc

    await db.commit()
    return RepoCreateResponse(repo_id=repo.id, status=RepoStatus(repo.status))


@router.get(
    "/repos/{repo_id}/status",
    response_model=RepoStatusResponse,
)
async def repo_status(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RepoStatusResponse:
    """Read indexing progress for a submitted repo.

    The DB row is the durable source of truth. Redis may hold more granular
    live per-stage progress while the worker is processing the job.
    """
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPO_NOT_FOUND", "message": f"Unknown repo_id: {repo_id}"},
        )

    live_state = await _read_job_state(redis, repo_id)
    return RepoStatusResponse(
        repo_id=repo_id,
        status=_status_from(repo.status, live_state),
        progress=_progress_from(repo.progress, live_state),
        stages=_stages_from(live_state),
        error=_error_from(repo.error, live_state),
    )


def _is_supported_git_url(url: str) -> bool:
    if not url:
        return False
    scp_like = _SCP_LIKE_GIT_URL.match(url)
    if scp_like:
        host = url.split("@", 1)[1].split(":", 1)[0]
        return _is_allowed_remote_host(host)

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_URL_SCHEMES:
        return False
    if not parsed.hostname:
        return False
    return _is_allowed_remote_host(parsed.hostname)


def _is_allowed_remote_host(host: str) -> bool:
    normalized = host.strip().strip("[]").rstrip(".").lower()
    if not normalized:
        return False
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return False

    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return True

    return not any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


async def _read_job_state(redis: Redis, repo_id: UUID) -> dict[str, object]:
    try:
        raw = await redis.get(job_state_key(str(repo_id)))
    except RedisError:
        return {}
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _status_from(db_status: str, live_state: dict[str, object]) -> RepoStatus:
    raw = live_state.get("status", db_status)
    try:
        return RepoStatus(str(raw))
    except ValueError:
        return RepoStatus(db_status)


def _progress_from(db_progress: int, live_state: dict[str, object]) -> int:
    raw = live_state.get("progress", db_progress)
    if not isinstance(raw, int | str):
        return db_progress
    try:
        progress = int(raw)
    except ValueError:
        return db_progress
    return progress if 0 <= progress <= 100 else db_progress


def _stages_from(live_state: dict[str, object]) -> StagesStatus:
    raw = live_state.get("stages")
    if not isinstance(raw, dict):
        return StagesStatus()
    values: dict[str, StageState] = {}
    for stage in ("cloning", "parsing", "embedding", "graphing"):
        try:
            values[stage] = StageState(str(raw[stage]))
        except (KeyError, ValueError):
            continue
    return StagesStatus(**values)


def _error_from(db_error: str | None, live_state: dict[str, object]) -> str | None:
    raw = live_state.get("error")
    return raw if isinstance(raw, str) else db_error
