"""Indexing pipeline orchestration — implements DESIGN.md §2.1.

Six stages, advanced as a strict monotonic state machine:
`queued → cloning → parsing → embedding → graphing → ready`
(or `→ failed` at any point, with error context preserved per D-2.1.4).
"""

import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from uuid import UUID

from dcode_shared.cache import job_state_key
from dcode_shared.db.models import Repo
from dcode_shared.db.session import SessionLocal
from dcode_shared.observability import log_event, structured_event
from dcode_shared.schemas import RepoStatus, StageState
from dcode_shared.settings import shared_settings
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from dcode_worker.context import PipelineContext
from dcode_worker.settings import worker_settings
from dcode_worker.stages import chunk, clone, embed, graph, parse

logger = logging.getLogger("dcode.worker.pipeline")

StageRunner = Callable[[PipelineContext], Awaitable[PipelineContext]]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
JOB_STATE_TTL_SECONDS = shared_settings.job_state_ttl_seconds


@dataclass(frozen=True)
class PipelineStage:
    """One externally visible pipeline state and its internal stage runners."""

    status: RepoStatus
    name: str
    runners: tuple[StageRunner, ...]
    in_progress: int
    done: int


DEFAULT_STAGES: tuple[PipelineStage, ...] = (
    PipelineStage(RepoStatus.cloning, "cloning", (clone.run,), 5, 20),
    PipelineStage(RepoStatus.parsing, "parsing", (parse.run, chunk.run), 25, 55),
    PipelineStage(RepoStatus.embedding, "embedding", (embed.run,), 60, 75),
    PipelineStage(RepoStatus.graphing, "graphing", (graph.run,), 80, 95),
)


async def handle_job(
    message_body: bytes,
    *,
    session_factory: SessionFactory = SessionLocal,
    redis_client: Redis | None = None,
    stages: Sequence[PipelineStage] = DEFAULT_STAGES,
) -> None:
    """Top-level handler for one RabbitMQ message.

    Advances the durable Repo state and the live Redis `job:{repo_id}` snapshot
    through the pipeline. Stage implementations are filled in by later roadmap
    items; this state machine already records their success or failure.
    """
    job = _parse_job(message_body)
    if job is None:
        return
    repo_id, repo_url = job

    log_event(logger, "index_job_received", repo_id=repo_id, repo_url=repo_url)
    ctx = PipelineContext(repo_id=str(repo_id), repo_url=repo_url)
    stage_states = _initial_stage_states(stages)

    owns_redis = redis_client is None
    redis = redis_client or Redis.from_url(worker_settings.redis_url, decode_responses=True)
    current_stage: PipelineStage | None = None

    try:
        async with session_factory() as db:
            for stage in stages:
                current_stage = stage
                stage_states[stage.name] = StageState.in_progress
                await _persist_state(
                    db,
                    redis,
                    repo_id,
                    stage.status,
                    stage.in_progress,
                    stage_states,
                    error=None,
                    complete=False,
                )
                log_event(
                    logger,
                    "stage_transition",
                    repo_id=repo_id,
                    stage=stage.name,
                    state="in_progress",
                    progress=stage.in_progress,
                )

                for runner in stage.runners:
                    ctx = await runner(ctx)

                stage_states[stage.name] = StageState.done
                await _persist_state(
                    db,
                    redis,
                    repo_id,
                    stage.status,
                    stage.done,
                    stage_states,
                    error=None,
                    complete=False,
                    commit_sha=ctx.commit_sha,
                )
                log_event(
                    logger,
                    "stage_transition",
                    repo_id=repo_id,
                    stage=stage.name,
                    state="done",
                    progress=stage.done,
                )

            await _persist_state(
                db,
                redis,
                repo_id,
                RepoStatus.ready,
                100,
                stage_states,
                error=None,
                complete=True,
                commit_sha=ctx.commit_sha,
            )
            log_event(logger, "index_job_completed", repo_id=repo_id, progress=100)
    except Exception as exc:  # noqa: BLE001 — stage failures are represented in job state
        error = str(exc) or exc.__class__.__name__
        if current_stage is not None:
            stage_states[current_stage.name] = StageState.failed
        async with session_factory() as db:
            await _persist_state(
                db,
                redis,
                repo_id,
                RepoStatus.failed,
                _failure_progress(current_stage),
                stage_states,
                error=error,
                complete=True,
                commit_sha=ctx.commit_sha,
            )
        logger.exception(structured_event("index_job_failed", repo_id=repo_id, error=error))
    finally:
        if owns_redis:
            await redis.aclose()


def _parse_job(message_body: bytes) -> tuple[UUID, str] | None:
    try:
        payload = json.loads(message_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.error("malformed job message; discarding")
        return None

    if not isinstance(payload, dict):
        logger.error("job payload is not an object: %s", payload)
        return None

    raw_repo_id = payload.get("repo_id")
    repo_url = payload.get("url")
    if not isinstance(raw_repo_id, str) or not isinstance(repo_url, str) or not repo_url:
        logger.error("job missing repo_id/url: %s", payload)
        return None

    try:
        return UUID(raw_repo_id), repo_url
    except ValueError:
        logger.error("job has invalid repo_id: %s", raw_repo_id)
        return None


def _initial_stage_states(stages: Sequence[PipelineStage]) -> dict[str, StageState]:
    return {stage.name: StageState.pending for stage in stages}


async def _persist_state(
    db: AsyncSession,
    redis: Redis,
    repo_id: UUID,
    status: RepoStatus,
    progress: int,
    stages: Mapping[str, StageState],
    *,
    error: str | None,
    complete: bool,
    commit_sha: str | None = None,
) -> None:
    await _update_repo(db, repo_id, status, progress, error, commit_sha)
    await _write_job_state(redis, repo_id, status, progress, stages, error=error, complete=complete)


async def _update_repo(
    db: AsyncSession,
    repo_id: UUID,
    status: RepoStatus,
    progress: int,
    error: str | None,
    commit_sha: str | None,
) -> None:
    repo = await db.get(Repo, repo_id)
    if repo is None:
        raise RuntimeError(f"repo row not found: {repo_id}")

    repo.status = status.value
    repo.progress = progress
    repo.error = error
    if commit_sha is not None:
        repo.commit_sha = commit_sha
    await db.commit()


async def _write_job_state(
    redis: Redis,
    repo_id: UUID,
    status: RepoStatus,
    progress: int,
    stages: Mapping[str, StageState],
    *,
    error: str | None,
    complete: bool,
) -> None:
    payload = _job_state_payload(status, progress, stages, error)
    key = job_state_key(str(repo_id))
    try:
        if complete:
            await redis.setex(key, JOB_STATE_TTL_SECONDS, payload)
        else:
            await redis.set(key, payload)
    except RedisError:
        logger.exception("failed to write Redis job state repo_id=%s", repo_id)


def _job_state_payload(
    status: RepoStatus,
    progress: int,
    stages: Mapping[str, StageState],
    error: str | None,
) -> str:
    return json.dumps(
        {
            "status": status.value,
            "progress": progress,
            "stages": {name: state.value for name, state in stages.items()},
            "error": error,
        },
        sort_keys=True,
    )


def _failure_progress(stage: PipelineStage | None) -> int:
    if stage is None:
        return 0
    return stage.in_progress
