"""Worker import + pipeline shape smoke tests."""

import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from uuid import uuid4

from dcode_shared.db.models import Repo
from dcode_shared.schemas import RepoStatus, StageState
from dcode_worker import pipeline
from dcode_worker.context import PipelineContext
from dcode_worker.stages import chunk, clone, embed, graph, parse
from sqlalchemy.ext.asyncio import AsyncSession


def test_pipeline_context_default_construction() -> None:
    ctx = PipelineContext(repo_id="r", repo_url="https://x.git")
    assert ctx.files == []
    assert ctx.chunks == []
    assert ctx.symbols == []
    assert ctx.edges == []


def test_all_stages_expose_run_coroutine() -> None:
    """Every stage module must expose `run` (filled in at M1/M2)."""
    for mod in (clone, parse, chunk, embed, graph):
        assert callable(mod.run)


async def test_handle_job_tolerates_malformed_message() -> None:
    """Skeleton: malformed JSON must not crash the consumer loop."""
    await pipeline.handle_job(b"not-json")
    await pipeline.handle_job(b'{"missing":"fields"}')


async def test_handle_job_advances_all_pipeline_states() -> None:
    repo = Repo(id=uuid4(), url="https://example.com/repo.git", status="queued", progress=0)
    session_factory = FakeSessionFactory(repo)
    redis = FakeRedis()
    calls: list[str] = []
    stages = (
        pipeline.PipelineStage(
            RepoStatus.cloning,
            "cloning",
            (_runner("clone", calls),),
            5,
            20,
        ),
        pipeline.PipelineStage(
            RepoStatus.parsing,
            "parsing",
            (_runner("parse", calls), _runner("chunk", calls)),
            25,
            55,
        ),
        pipeline.PipelineStage(
            RepoStatus.embedding,
            "embedding",
            (_runner("embed", calls),),
            60,
            75,
        ),
        pipeline.PipelineStage(
            RepoStatus.graphing,
            "graphing",
            (_runner("graph", calls),),
            80,
            95,
        ),
    )

    await pipeline.handle_job(
        json.dumps({"repo_id": str(repo.id), "url": repo.url}).encode(),
        session_factory=session_factory,
        redis_client=redis,
        stages=stages,
    )

    assert calls == ["clone", "parse", "chunk", "embed", "graph"]
    assert session_factory.commits == 9
    assert repo.status == RepoStatus.ready.value
    assert repo.progress == 100
    assert repo.error is None

    state = redis.json_state(str(repo.id))
    assert state["status"] == RepoStatus.ready.value
    assert state["progress"] == 100
    assert state["error"] is None
    assert state["stages"] == {
        "cloning": StageState.done.value,
        "parsing": StageState.done.value,
        "embedding": StageState.done.value,
        "graphing": StageState.done.value,
    }
    assert redis.expirations[str(repo.id)] == pipeline.JOB_STATE_TTL_SECONDS


async def test_handle_job_marks_current_stage_failed() -> None:
    repo = Repo(id=uuid4(), url="https://example.com/repo.git", status="queued", progress=0)
    session_factory = FakeSessionFactory(repo)
    redis = FakeRedis()
    calls: list[str] = []
    stages = (
        pipeline.PipelineStage(
            RepoStatus.cloning,
            "cloning",
            (_runner("clone", calls),),
            5,
            20,
        ),
        pipeline.PipelineStage(
            RepoStatus.parsing,
            "parsing",
            (_failing_runner("parse", calls), _runner("chunk", calls)),
            25,
            55,
        ),
    )

    await pipeline.handle_job(
        json.dumps({"repo_id": str(repo.id), "url": repo.url}).encode(),
        session_factory=session_factory,
        redis_client=redis,
        stages=stages,
    )

    assert calls == ["clone", "parse"]
    assert repo.status == RepoStatus.failed.value
    assert repo.progress == 25
    assert repo.error == "parse failed"

    state = redis.json_state(str(repo.id))
    assert state["status"] == RepoStatus.failed.value
    assert state["stages"]["cloning"] == StageState.done.value
    assert state["stages"]["parsing"] == StageState.failed.value
    assert redis.expirations[str(repo.id)] == pipeline.JOB_STATE_TTL_SECONDS


async def test_handle_job_emits_structured_stage_logs(caplog) -> None:
    caplog.set_level(logging.INFO, logger="dcode.worker.pipeline")
    repo = Repo(id=uuid4(), url="https://example.com/repo.git", status="queued", progress=0)

    await pipeline.handle_job(
        json.dumps({"repo_id": str(repo.id), "url": repo.url}).encode(),
        session_factory=FakeSessionFactory(repo),
        redis_client=FakeRedis(),
        stages=(
            pipeline.PipelineStage(
                RepoStatus.cloning,
                "cloning",
                (_runner("clone", []),),
                5,
                20,
            ),
        ),
    )

    messages = [record.message for record in caplog.records]
    assert any('"event": "index_job_received"' in message for message in messages)
    assert any('"event": "stage_transition"' in message for message in messages)
    assert any('"event": "index_job_completed"' in message for message in messages)


async def test_embedding_stub_returns_zero_vectors_of_configured_dim() -> None:
    stub = embed.StubEmbeddingClient(dim=16)
    vecs = await stub.embed_batch(["a", "b", "c"])
    assert len(vecs) == 3
    assert all(len(v) == 16 for v in vecs)
    assert all(all(x == 0.0 for x in v) for v in vecs)


class FakeSession(AbstractAsyncContextManager[AsyncSession]):
    def __init__(self, repo: Repo | None, factory: "FakeSessionFactory") -> None:
        self.repo = repo
        self.factory = factory

    async def __aenter__(self) -> AsyncSession:
        return self  # type: ignore[return-value]

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def get(self, model: type[Repo], repo_id: object) -> Repo | None:
        if model is Repo and self.repo is not None and self.repo.id == repo_id:
            return self.repo
        return None

    async def commit(self) -> None:
        self.factory.commits += 1


class FakeSessionFactory:
    def __init__(self, repo: Repo | None) -> None:
        self.repo = repo
        self.commits = 0

    def __call__(self) -> AbstractAsyncContextManager[AsyncSession]:
        return FakeSession(self.repo, self)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.expirations[key.removeprefix("job:")] = ttl

    def json_state(self, repo_id: str) -> dict[str, object]:
        return json.loads(self.values[f"job:{repo_id}"])


def _runner(
    name: str,
    calls: list[str],
) -> Callable[[PipelineContext], Awaitable[PipelineContext]]:
    async def run(ctx: PipelineContext) -> PipelineContext:
        calls.append(name)
        return ctx

    return run


def _failing_runner(
    name: str,
    calls: list[str],
) -> Callable[[PipelineContext], Awaitable[PipelineContext]]:
    async def run(ctx: PipelineContext) -> PipelineContext:
        calls.append(name)
        raise RuntimeError(f"{name} failed")

    return run
