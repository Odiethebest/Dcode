"""Redis cache key helpers — implements DESIGN.md §3.3 Redis Key Naming Convention.

Keep all key construction here. Callers MUST NOT build keys by string formatting
inline; that diverges from spec and breaks cache lookups across services.
"""

import hashlib
import json
from typing import Any


def embedding_cache_key(model_id: str, text: str) -> str:
    """`embed:{model_id}:{sha256(text)}` — TTL: forever."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embed:{model_id}:{digest}"


def tool_cache_key(tool_name: str, repo_id: str, args: dict[str, Any]) -> str:
    """`tool:{tool_name}:{repo_id}:{args_hash}` — TTL: 24h (DESIGN.md D-2.3.2)."""
    return f"tool:{tool_name}:{repo_id}:{_hash_args(args)}"


def query_cache_key(repo_id: str, query: str) -> str:
    """`query:{repo_id}:{query_hash}` — TTL: 1h."""
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:32]
    return f"query:{repo_id}:{digest}"


def job_state_key(repo_id: str) -> str:
    """`job:{repo_id}` — TTL: 7 days after completion."""
    return f"job:{repo_id}"


def _hash_args(args: dict[str, Any]) -> str:
    """Canonical, sort-stable JSON hash for cache args."""
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
