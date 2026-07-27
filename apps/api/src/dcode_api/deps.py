"""FastAPI dependency providers — DB, Redis, RabbitMQ, agent client.

Redis and the agent httpx client are process-wide singletons whose lifecycle is
owned by the app lifespan (`warm_pools` / `close_pools`, wired in main.py);
`get_db` draws from the shared SQLAlchemy async engine pool. RabbitMQ still
connects per publish (infrequent submit path).
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

import aio_pika
import httpx
from dcode_shared.db.session import SessionLocal
from dcode_shared.internal import internal_auth_headers
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from dcode_api.settings import api_settings

_redis: Redis | None = None
_agent_client: httpx.AsyncClient | None = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session (auto-closed)."""
    async with SessionLocal() as session:
        yield session


def _create_redis() -> Redis:
    return Redis.from_url(api_settings.redis_url, decode_responses=True)


async def get_redis() -> Redis:
    """Return the process-wide Redis client (warmed in lifespan; lazy fallback)."""
    global _redis
    if _redis is None:
        _redis = _create_redis()
    return _redis


async def publish_index_job(repo_id: UUID, repo_url: str) -> None:
    """Publish one durable indexing job to RabbitMQ."""
    connection = await aio_pika.connect_robust(api_settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.declare_queue(api_settings.index_queue_name, durable=True)
        payload = json.dumps({"repo_id": str(repo_id), "url": repo_url}).encode("utf-8")
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=payload,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=api_settings.index_queue_name,
        )


async def get_index_job_publisher() -> Callable[[UUID, str], Awaitable[None]]:
    """Dependency wrapper so tests can replace RabbitMQ publishing."""
    return publish_index_job


def _create_agent_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=api_settings.agent_url,
        timeout=httpx.Timeout(60.0, connect=5.0),
        headers=internal_auth_headers(api_settings.internal_api_key),
    )


async def get_agent_client() -> httpx.AsyncClient:
    """Return the process-wide httpx client targeting the agent service.

    TODO(M2): tune timeouts/retries per NFR-2 (TTFB ≤ 3s).
    """
    global _agent_client
    if _agent_client is None:
        _agent_client = _create_agent_client()
    return _agent_client


def warm_pools() -> None:
    """Instantiate the shared Redis + agent clients at startup so they are owned
    by the app lifespan rather than created lazily on the first request."""
    global _redis, _agent_client
    if _redis is None:
        _redis = _create_redis()
    if _agent_client is None:
        _agent_client = _create_agent_client()


async def close_pools() -> None:
    """Release the shared Redis + agent clients on shutdown."""
    global _redis, _agent_client
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    if _agent_client is not None:
        await _agent_client.aclose()
        _agent_client = None
