"""Pipeline stage: batch embedding with Redis content-addressed cache.

Implements DESIGN.md §2.1 'Embed' stage and D-2.1.3 (cache key
`embed:{model_id}:{sha256(text)}`, TTL forever).

The embedding model is Open Decision OD-2 (see PLAN.md §9). Client
implementations live in ``dcode_shared.embedding``.
"""

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import cast
from uuid import UUID

from dcode_shared.cache import embedding_cache_key
from dcode_shared.db.models import Chunk as DBChunk
from dcode_shared.db.session import SessionLocal
from dcode_shared.embedding import (
    EmbeddingClient,
    create_embedding_client,
)
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from dcode_worker.context import PipelineContext
from dcode_worker.models import CodeChunk
from dcode_worker.settings import worker_settings

logger = logging.getLogger("dcode.worker.stages.embed")

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def run(
    ctx: PipelineContext,
    *,
    session_factory: SessionFactory = SessionLocal,
    redis_client: Redis | None = None,
    embedding_client: EmbeddingClient | None = None,
    model_id: str | None = None,
    embedding_dim: int | None = None,
) -> PipelineContext:
    """Embed chunks, cache vectors, and persist chunk rows to Postgres."""
    dim = embedding_dim or worker_settings.embedding_dim
    model = model_id or worker_settings.embedding_model
    client = embedding_client or create_embedding_client(
        model=model,
        dim=dim,
        endpoint=worker_settings.embedding_endpoint,
        batch_size=worker_settings.embedding_batch_size,
        max_retries=worker_settings.embedding_max_retries,
    )

    owns_redis = redis_client is None
    redis = redis_client or Redis.from_url(worker_settings.redis_url, decode_responses=True)

    try:
        vectors = await _embed_chunks(ctx.chunks, redis, client, model_id=model, embedding_dim=dim)
        async with session_factory() as db:
            await _replace_repo_chunks(db, UUID(ctx.repo_id), ctx.chunks, vectors)
        ctx.embeddings = vectors
        return ctx
    finally:
        if owns_redis:
            await redis.aclose()


async def _embed_chunks(
    chunks: list[CodeChunk],
    redis: Redis,
    client: EmbeddingClient,
    *,
    model_id: str,
    embedding_dim: int,
) -> list[list[float]]:
    if not chunks:
        return []

    keys = [embedding_cache_key(model_id, chunk.content) for chunk in chunks]
    cached = await _read_cached_vectors(redis, keys, embedding_dim)

    missing_indexes = [index for index, vector in enumerate(cached) if vector is None]
    if missing_indexes:
        texts = [chunks[index].content for index in missing_indexes]
        embedded = await client.embed_batch(texts)
        if len(embedded) != len(missing_indexes):
            raise RuntimeError(
                "embedding client returned a different number of vectors than inputs"
            )

        cache_updates: dict[str, str] = {}
        for index, vector in zip(missing_indexes, embedded, strict=True):
            validated = _validate_vector(vector, embedding_dim)
            cached[index] = validated
            cache_updates[keys[index]] = json.dumps(validated)
        await _write_cached_vectors(redis, cache_updates)

    return [vector for vector in cached if vector is not None]


async def _read_cached_vectors(
    redis: Redis,
    keys: list[str],
    embedding_dim: int,
) -> list[list[float] | None]:
    try:
        raw_values = cast(list[object | None], await redis.mget(keys))
    except RedisError:
        logger.exception("failed to read embedding cache; falling back to embedding all chunks")
        return [None] * len(keys)

    return [_decode_cached_vector(raw, embedding_dim) for raw in raw_values]


async def _write_cached_vectors(redis: Redis, values: Mapping[str, str]) -> None:
    if not values:
        return
    try:
        await redis.mset(values)
    except RedisError:
        logger.exception("failed to write embedding cache")


def _decode_cached_vector(raw: object, embedding_dim: int) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    try:
        return _validate_vector(parsed, embedding_dim)
    except ValueError:
        return None


def _validate_vector(vector: Sequence[object], embedding_dim: int) -> list[float]:
    if len(vector) != embedding_dim:
        raise ValueError(
            f"embedding dimension mismatch: expected {embedding_dim}, got {len(vector)}"
        )

    values: list[float] = []
    for value in vector:
        if not isinstance(value, int | float):
            raise ValueError("embedding vector contains a non-numeric value")
        values.append(float(value))
    return values


async def _replace_repo_chunks(
    db: AsyncSession,
    repo_id: UUID,
    chunks: list[CodeChunk],
    vectors: list[list[float]],
) -> None:
    if len(chunks) != len(vectors):
        raise RuntimeError("chunk/vector count mismatch")

    await db.execute(delete(DBChunk).where(DBChunk.repo_id == repo_id))
    rows = [
        DBChunk(
            repo_id=repo_id,
            file_path=chunk.file_path,
            chunk_type=chunk.chunk_type.value,
            parent_symbol=chunk.parent_symbol,
            symbol_name=chunk.symbol_name,
            signature=chunk.signature,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            imports=chunk.imports,
            content=chunk.content,
            embedding=vector,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    db.add_all(rows)
    await db.commit()
