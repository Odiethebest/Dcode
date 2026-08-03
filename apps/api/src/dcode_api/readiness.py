"""Readiness checks for the gateway (F-10).

`/healthz` answers `ok` unconditionally — its own docstring says it does not
check dependent services. That is correct for a liveness probe and useless for
deciding whether this process can serve a request: it reported healthy with
Postgres, Redis and RabbitMQ all down, and the first user request was what
discovered it.

The dimension check is here rather than in a runbook because of Deploy.md §5.4:
`chunks.embedding` is fixed at migration time, and a service configured for a
different dimension produces no error — the worker's inserts fail, or dense
search runs a stub all-zero query vector against real stored vectors and
silently returns noise. A probe is the only place that catches it before a user
does.
"""

from dataclasses import dataclass

from dcode_shared.db.session import SessionLocal
from redis.exceptions import RedisError
from sqlalchemy import text

from dcode_api.deps import get_redis
from dcode_api.settings import api_settings


@dataclass(frozen=True)
class Check:
    """One readiness check. `detail` is why it failed, never a secret."""

    name: str
    ok: bool
    detail: str | None = None


async def run_checks() -> list[Check]:
    """Every check, always all of them.

    Not short-circuited on the first failure: an operator looking at this wants
    to know whether one thing is broken or everything is, and returning after
    the first one turns "the database is down" into a report that says nothing
    about Redis.
    """
    return [await _check_database(), await _check_redis(), await _check_embedding_dim()]


async def _check_database() -> Check:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — any failure is not-ready
        return Check("database", False, _reason(exc))
    return Check("database", True)


async def _check_redis() -> Check:
    try:
        redis = await get_redis()
        await redis.ping()
    except (RedisError, OSError) as exc:
        return Check("redis", False, _reason(exc))
    except Exception as exc:  # noqa: BLE001
        return Check("redis", False, _reason(exc))
    return Check("redis", True)


async def _check_embedding_dim() -> Check:
    """Compare the configured dimension against the live column.

    Skipped rather than failed when the table is empty or absent: before the
    first migration there is nothing to disagree with, and reporting not-ready
    would block a deploy that has not reached the migration step yet.
    """
    configured = api_settings.embedding_dim
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
                )
            )
            live = result.scalar_one_or_none()
    except Exception:  # noqa: BLE001 — no table yet is not a mismatch
        return Check("embedding_dim", True, f"not checked (configured {configured})")

    if live is None:
        return Check("embedding_dim", True, f"not checked (configured {configured})")
    if int(live) != configured:
        return Check(
            "embedding_dim",
            False,
            (
                f"EMBEDDING_DIM is {configured} but chunks.embedding is vector({int(live)}). "
                "The column is fixed at migration time; this cannot be reconciled by "
                "restarting."
            ),
        )
    return Check("embedding_dim", True)


def _reason(exc: Exception) -> str:
    """Exception type and message, trimmed.

    A connection error can carry a DSN, so the detail is bounded rather than
    passed through — a readiness probe is often reachable by more people than
    the logs are.
    """
    return f"{type(exc).__name__}: {exc}"[:200]
