"""Embedding cache and chunk persistence tests."""

import json
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from uuid import uuid4

from dcode_shared.cache import embedding_cache_key
from dcode_shared.embedding import EmbeddingClient
from dcode_shared.schemas import ChunkType
from dcode_worker.context import PipelineContext
from dcode_worker.models import CodeChunk
from dcode_worker.stages import embed
from pytest import raises
from sqlalchemy.ext.asyncio import AsyncSession


async def test_embed_stage_uses_cache_and_persists_chunks() -> None:
    repo_id = uuid4()
    first = _chunk("one", "def one():\n    return 1\n")
    second = _chunk("two", "def two():\n    return 2\n")
    cached_key = embedding_cache_key("stub-test", first.content)
    redis = FakeRedis({cached_key: json.dumps([1.0, 2.0])})
    session_factory = FakeSessionFactory()
    client = RecordingEmbeddingClient([[3.0, 4.0]])
    ctx = PipelineContext(
        repo_id=str(repo_id),
        repo_url="file:///unused",
        chunks=[first, second],
    )

    result = await embed.run(
        ctx,
        session_factory=session_factory,
        redis_client=redis,
        embedding_client=client,
        model_id="stub-test",
        embedding_dim=2,
    )

    assert client.calls == [[second.content]]
    assert result.embeddings == [[1.0, 2.0], [3.0, 4.0]]
    assert redis.mset_calls == [
        {embedding_cache_key("stub-test", second.content): json.dumps([3.0, 4.0])}
    ]
    assert session_factory.session.commits == 1
    assert len(session_factory.session.rows) == 2
    assert session_factory.session.rows[0].repo_id == repo_id
    assert session_factory.session.rows[0].symbol_name == "one"
    assert session_factory.session.rows[0].embedding == [1.0, 2.0]
    assert session_factory.session.rows[1].embedding == [3.0, 4.0]


async def test_embed_stage_rejects_wrong_vector_dimension() -> None:
    ctx = PipelineContext(
        repo_id=str(uuid4()),
        repo_url="file:///unused",
        chunks=[_chunk("bad", "def bad():\n    return None\n")],
    )

    with raises(ValueError, match="embedding dimension mismatch"):
        await embed.run(
            ctx,
            session_factory=FakeSessionFactory(),
            redis_client=FakeRedis({}),
            embedding_client=RecordingEmbeddingClient([[1.0]]),
            model_id="stub-test",
            embedding_dim=2,
        )


def _chunk(symbol_name: str, content: str) -> CodeChunk:
    return CodeChunk(
        file_path="pkg/example.py",
        chunk_type=ChunkType.function,
        parent_symbol=None,
        symbol_name=symbol_name,
        signature=f"def {symbol_name}()",
        start_line=1,
        end_line=2,
        imports=["import os"],
        content=content,
    )


class RecordingEmbeddingClient(EmbeddingClient):
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return self.vectors


class FakeRedis:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.mget_calls: list[list[str]] = []
        self.mset_calls: list[dict[str, str]] = []

    async def mget(self, keys: Sequence[str]) -> list[str | None]:
        key_list = list(keys)
        self.mget_calls.append(key_list)
        return [self.values.get(key) for key in key_list]

    async def mset(self, values: dict[str, str]) -> None:
        self.values.update(values)
        self.mset_calls.append(values)


class FakeSession(AbstractAsyncContextManager[AsyncSession]):
    def __init__(self) -> None:
        self.rows: list[object] = []
        self.commits = 0
        self.executed = 0

    async def __aenter__(self) -> AsyncSession:
        return self  # type: ignore[return-value]

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def execute(self, statement: object) -> None:
        self.executed += 1

    def add_all(self, rows: list[object]) -> None:
        self.rows.extend(rows)

    async def commit(self) -> None:
        self.commits += 1


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session = FakeSession()

    def __call__(self) -> AbstractAsyncContextManager[AsyncSession]:
        return self.session
