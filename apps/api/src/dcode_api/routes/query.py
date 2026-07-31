"""Public query endpoint and agent SSE proxy.

Architecture: the API gateway proxies POST /api/v1/query to the Agent
service's /internal/query, streaming SSE events back unchanged. This keeps
the agent fully isolated and lets it be scaled / replaced independently.

If the agent service is unreachable, emit one explicitly labelled stub
`thought` plus an `error` event so the SSE protocol terminates honestly.
"""

from collections.abc import AsyncIterator

import httpx
from dcode_shared.cache import query_cache_key
from dcode_shared.events import ErrorEvent, ThoughtEvent, sse_encode
from dcode_shared.schemas import QueryRequest, QueryTurn
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from dcode_api.deps import get_agent_client, get_redis
from dcode_api.settings import api_settings

router = APIRouter(tags=["query"])


@router.post("/query")
async def query(
    body: QueryRequest,
    agent: httpx.AsyncClient = Depends(get_agent_client),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    """Stream SSE events from the agent service back to the client.

    Successful streams are cached in Redis under the documented
    `query:{repo_id}:{hash(query)}` key for a short replay window.
    """
    return StreamingResponse(
        _stream_query(agent, redis, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )


async def _stream_query(
    agent: httpx.AsyncClient,
    redis: Redis,
    body: QueryRequest,
) -> AsyncIterator[bytes]:
    # Bound history once so the planner, the proxied agent body, and the cache
    # key all see the same trimmed turns.
    body.history = _bounded_history(body.history)
    cache_key = query_cache_key(
        str(body.repo_id),
        body.query,
        history=[turn.model_dump() for turn in body.history],
    )
    cached = await _query_cache_get(redis, cache_key)
    if cached is not None:
        yield cached.encode("utf-8")
        return

    buffered = bytearray()
    async for chunk in _proxy_to_agent(agent, body):
        buffered.extend(chunk)
        yield chunk

    if buffered and b"event: error\n" not in buffered:
        await _query_cache_set(redis, cache_key, buffered.decode("utf-8"))


async def _proxy_to_agent(
    agent: httpx.AsyncClient, body: QueryRequest
) -> AsyncIterator[bytes]:
    try:
        async with agent.stream(
            "POST",
            "/internal/query",
            json=body.model_dump(mode="json"),
        ) as response:
            if response.status_code != 200:
                yield sse_encode(
                    "error",
                    ErrorEvent(
                        code="AGENT_UNAVAILABLE",
                        message=f"upstream returned {response.status_code}",
                    ),
                )
                return
            async for chunk in response.aiter_bytes():
                yield chunk
    except httpx.RequestError as exc:
        # Emit one explicitly labelled stub thought so the SSE protocol still
        # terminates honestly when the agent service is offline.
        yield sse_encode(
            "thought",
            ThoughtEvent(
                step=1,
                content="(skeleton) agent service unreachable; emitting stub event",
            ),
        )
        yield sse_encode(
            "error",
            ErrorEvent(code="AGENT_UNAVAILABLE", message=str(exc)),
        )


def _bounded_history(history: list[QueryTurn]) -> list[QueryTurn]:
    """Trim conversation history to the gateway's turn / char budget.

    Bounds protect the planner context, the LLM token budget, and the cache
    key. The most recent turns are kept (oldest dropped first) and each turn's
    content is clipped; the newest turn is clipped to the remaining budget
    rather than dropped, so a follow-up never loses its immediate context.
    """
    if not history:
        return []
    max_turns = api_settings.query_history_max_turns
    max_total = api_settings.query_history_max_chars
    max_turn = api_settings.query_history_max_turn_chars

    recent = history[-max_turns:] if max_turns > 0 else list(history)
    bounded: list[QueryTurn] = []
    total = 0
    for turn in reversed(recent):  # newest first, so the freshest context wins
        if max_total > 0 and total >= max_total:
            break
        content = turn.content
        if max_turn > 0:
            content = content[:max_turn]
        if max_total > 0:
            content = content[: max_total - total]
        if not content:
            continue
        total += len(content)
        bounded.append(QueryTurn(role=turn.role, content=content))
    bounded.reverse()
    return bounded


async def _query_cache_get(redis: Redis, key: str) -> str | None:
    try:
        cached = await redis.get(key)
    except RedisError:
        return None
    if isinstance(cached, bytes):
        return cached.decode("utf-8")
    return cached if isinstance(cached, str) else None


async def _query_cache_set(redis: Redis, key: str, value: str) -> None:
    try:
        await redis.setex(key, api_settings.query_cache_ttl_seconds, value)
    except RedisError:
        return
