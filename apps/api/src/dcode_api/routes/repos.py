"""Public repository submission and indexing-status endpoints."""

import asyncio
import ipaddress
import json
import re
import socket
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
from dcode_api.settings import api_settings

router = APIRouter(tags=["repos"])

_SCP_LIKE_GIT_URL = re.compile(r"^[\w.-]+@[\w.-]+:[\w./-]+(?:\.git)?$")
_ALLOWED_URL_SCHEMES = {"https", "http", "ssh", "git"}
_DNS_TIMEOUT_SECONDS = 3.0


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
    rejection = await _reject_repo_url(repo_url)
    if rejection is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REPO_URL", "message": rejection},
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


async def _reject_repo_url(url: str) -> str | None:
    """Why this URL may not be cloned, or None. The message reaches the caller.

    Three checks beyond the syntax one, in order of how much they buy:

    1. **No credentials in the URL.** `https://user:token@host/...` was accepted
       and then persisted into `repos.url` and echoed back by the status route,
       so a token handed to this endpoint became readable by anyone who could
       read a repository's status. Rejected rather than stripped: quietly
       mutating what someone submitted is worse than saying no.
    2. **An optional host allowlist.** Empty by default, which keeps any public
       host acceptable. Set `REPO_URL_ALLOWED_HOSTS` and it becomes the strong
       control — everything else here is a filter on what is obviously wrong,
       and this is the only rule that states what is right.
    3. **Resolution.** The literal-IP check never fired for a *name*, so
       `evil.example.com` pointing at `169.254.169.254` or `10.0.0.1` passed.
       Every resolved address is now checked.

    What check 3 does **not** close is rebinding: git resolves the name again
    when it clones, and a DNS answer that changes in between defeats this. The
    fix for that is egress filtering at the network, not more code here, and it
    is recorded as such in Deploy.md rather than implied to be handled.
    """
    if not url:
        return "Expected a Git URL."

    scp_like = _SCP_LIKE_GIT_URL.match(url)
    if scp_like:
        host = url.split("@", 1)[1].split(":", 1)[0]
    else:
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_URL_SCHEMES:
            return "Expected an http(s), ssh, git, or git@host:path Git URL."
        if parsed.password is not None or (parsed.username and parsed.scheme != "ssh"):
            return (
                "Remove the credentials from the URL. This endpoint indexes public "
                "repositories, and a submitted URL is stored and shown in status responses."
            )
        if not parsed.hostname:
            return "Expected an http(s), ssh, git, or git@host:path Git URL."
        host = parsed.hostname

    if not _is_allowed_remote_host(host):
        return "That host is not a permitted clone target."

    allowlist = api_settings.repo_url_allowed_hosts_list
    normalized = host.strip().strip("[]").rstrip(".").lower()
    if allowlist and not any(
        normalized == allowed or normalized.endswith(f".{allowed}") for allowed in allowlist
    ):
        return f"Only these hosts may be cloned: {', '.join(sorted(allowlist))}."

    unreachable = await _reject_resolved_addresses(normalized)
    if unreachable is not None:
        return unreachable
    return None


async def resolve_host(host: str) -> list[str]:
    """Addresses `host` resolves to.

    A module-level function rather than an inline `loop.getaddrinfo` so it can
    be replaced in tests. Without a seam here, every test that submits a
    repository URL performs a real DNS lookup — which makes the suite depend on
    the network, and makes CI slower and occasionally wrong for a reason that
    has nothing to do with the code under test.
    """
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(
        loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP),
        timeout=_DNS_TIMEOUT_SECONDS,
    )
    return [str(info[4][0]) for info in infos]


async def _reject_resolved_addresses(host: str) -> str | None:
    """Resolve `host` and refuse if any answer is a non-public address."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        # A literal was already checked by _is_allowed_remote_host.
        return None

    try:
        addresses = await resolve_host(host)
    except (TimeoutError, OSError):
        # Refusing here would make an unrelated DNS hiccup look like a rejected
        # URL, and the worker's clone would fail anyway with a clearer reason.
        return None

    for address in addresses:
        if not _is_allowed_remote_host(address):
            return (
                f"{host} resolves to a private or reserved address "
                "and will not be cloned."
            )
    return None


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
