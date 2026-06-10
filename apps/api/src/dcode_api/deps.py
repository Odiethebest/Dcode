"""FastAPI dependency providers — DB, Redis, RabbitMQ, agent client.

Skeleton uses simple module-level singletons. M2 will move pool lifecycle
into the lifespan handler in main.py for graceful startup / shutdown.
"""

from collections.abc import AsyncIterator

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from dcode_api.settings import api_settings
from dcode_shared.db.session import SessionLocal

_redis: Redis | None = None
_agent_client: httpx.AsyncClient | None = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session (auto-closed)."""
    async with SessionLocal() as session:
        yield session


async def get_redis() -> Redis:
    """Return a process-wide Redis client (lazy init).

    TODO(M2): replace module singleton with lifespan-managed connection pool.
    """
    global _redis
    if _redis is None:
        _redis = Redis.from_url(api_settings.redis_url, decode_responses=True)
    return _redis


async def get_agent_client() -> httpx.AsyncClient:
    """Return a process-wide httpx client targeting the agent service.

    TODO(M2): tune timeouts/retries per NFR-2 (TTFB ≤ 3s).
    """
    global _agent_client
    if _agent_client is None:
        _agent_client = httpx.AsyncClient(
            base_url=api_settings.agent_url,
            timeout=httpx.Timeout(60.0, connect=5.0),
        )
    return _agent_client
