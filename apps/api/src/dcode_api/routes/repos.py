"""Public repository submission and indexing-status endpoints."""

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
    RepoListResponse,
    RepoStatus,
    RepoStatusResponse,
    RepoSummary,
    StagesStatus,
    StageState,
)
from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
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
    response: Response,
    db: AsyncSession = Depends(get_db),
    publish_job: Callable[[UUID, str], Awaitable[None]] = Depends(get_index_job_publisher),
) -> RepoCreateResponse:
    """Submit a repository for indexing.

    Idempotent on the repository URL: if the same repo is already indexed or
    still indexing, that one is returned instead of cloning it again. Otherwise
    persists a queued Repo row, commits it so the worker can read it, then
    publishes the indexing job to RabbitMQ. If publishing fails after the row
    is durable, the repo is marked failed rather than left queued forever.
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

    existing = await _find_reusable_repo(db, repo_url)
    if existing is not None:
        # Nothing was accepted for processing, so 202 would be a lie.
        response.status_code = status.HTTP_200_OK
        return RepoCreateResponse(
            repo_id=existing.id,
            status=RepoStatus(existing.status),
            reused=True,
        )

    repo = Repo(url=repo_url, status=RepoStatus.queued.value, progress=0)
    db.add(repo)
    await db.flush()
    await db.commit()

    try:
        await publish_job(repo.id, repo_url)
    except Exception as exc:  # noqa: BLE001 — convert infra failures to API errors
        repo.status = RepoStatus.failed.value
        repo.error = "Repository was not queued because RabbitMQ publish failed."
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "INDEX_QUEUE_UNAVAILABLE",
                "message": "Repository was not queued because RabbitMQ publish failed.",
            },
        ) from exc

    return RepoCreateResponse(repo_id=repo.id, status=RepoStatus(repo.status), reused=False)


# Statuses that mean "this repo is already indexed, or on its way there" —
# resubmitting should join them, not start a second clone of the same code.
_REUSABLE_STATUSES = (
    RepoStatus.ready,
    RepoStatus.graphing,
    RepoStatus.embedding,
    RepoStatus.parsing,
    RepoStatus.cloning,
    RepoStatus.queued,
)


def _url_variants(url: str) -> list[str]:
    """Spellings of the same remote that should collide.

    Deliberately narrow: trailing slashes, the `.git` suffix, and the case of
    scheme/host — the ways one person retyping one URL differs from themselves.
    Path case is preserved, since not every host treats it as insensitive, and
    merging two genuinely different repos is a worse failure than one duplicate.
    """
    trimmed = url.strip().rstrip("/")
    parsed = urlparse(trimmed)
    if parsed.scheme and parsed.hostname:
        host = parsed.hostname.lower()
        netloc = f"{host}:{parsed.port}" if parsed.port else host
        trimmed = parsed._replace(scheme=parsed.scheme.lower(), netloc=netloc).geturl()

    base = trimmed[: -len(".git")] if trimmed.endswith(".git") else trimmed
    return list({url, trimmed, base, f"{base}.git", f"{base}/"})


async def _find_reusable_repo(db: AsyncSession, url: str) -> Repo | None:
    """The repo to hand back instead of re-cloning, if there is one.

    Prefers `ready`, then anything still indexing, and ignores `failed` rows
    entirely — a previous failure is exactly when the user does want a retry.

    Two simultaneous submits of the same URL can still both miss this check and
    create two rows; closing that needs a uniqueness constraint on a normalised
    URL column, i.e. a migration. The bug this fixes is one person clicking
    Index twice, which is sequential.
    """
    result = await db.execute(
        select(Repo)
        .where(Repo.url.in_(_url_variants(url)))
        .where(Repo.status.in_([s.value for s in _REUSABLE_STATUSES]))
        .order_by(Repo.created_at.desc())
    )
    candidates = list(result.scalars().all())
    if not candidates:
        return None

    by_status = {status_.value: status_ for status_ in _REUSABLE_STATUSES}
    return min(
        candidates,
        key=lambda repo: _REUSABLE_STATUSES.index(by_status[repo.status]),
    )


# One page, capped. There is no pagination API and inventing one for a demo
# with a handful of repositories would be scope the product does not have —
# but returning "everything" from a table that only grows is how a list
# endpoint becomes a slow query later, so the cap is explicit and reported.
_REPO_LIST_LIMIT = 50


@router.get("/repos", response_model=RepoListResponse)
async def list_repos(db: AsyncSession = Depends(get_db)) -> RepoListResponse:
    """List indexed repositories, most recently created first.

    Reads Postgres only. Deliberately no Redis overlay: this answers "what can
    I select?", and per-stage live progress belongs to the status route for the
    one repository actually being watched.
    """
    result = await db.execute(
        select(Repo).order_by(Repo.created_at.desc()).limit(_REPO_LIST_LIMIT + 1)
    )
    rows = list(result.scalars().all())
    truncated = len(rows) > _REPO_LIST_LIMIT
    return RepoListResponse(
        repos=[
            RepoSummary(repo_id=repo.id, url=repo.url, status=_coerce_status(repo.status))
            for repo in rows[:_REPO_LIST_LIMIT]
        ],
        truncated=truncated,
    )


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
        url=repo.url,
        status=_status_from(repo.status, live_state),
        progress=_progress_from(repo.progress, live_state),
        stages=_stages_from(live_state),
        error=_error_from(repo.error, live_state),
        warnings=_warnings_from(live_state),
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


def _coerce_status(db_status: str) -> RepoStatus:
    """Row status as an enum, falling back to `failed` for an unknown value.

    `failed` rather than `ready`: a status this code does not recognise is not
    something to present as selectable. The list would otherwise offer a
    repository that cannot answer anything.
    """
    try:
        return RepoStatus(db_status)
    except ValueError:
        return RepoStatus.failed


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


def _warnings_from(live_state: dict[str, object]) -> list[str]:
    raw = live_state.get("warnings")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]
