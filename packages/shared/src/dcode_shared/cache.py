"""Redis cache key helpers — implements DESIGN.md §3.3 Redis Key Naming Convention.

Keep all key construction here. Callers MUST NOT build keys by string formatting
inline; that diverges from spec and breaks cache lookups across services.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


def embedding_cache_key(model_id: str, text: str) -> str:
    """`embed:{model_id}:{sha256(text)}` — TTL: forever."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embed:{model_id}:{digest}"


def tool_cache_key(tool_name: str, repo_id: str, args: dict[str, Any]) -> str:
    """`tool:{tool_name}:{repo_id}:{args_hash}` — TTL: 24h (DESIGN.md D-2.3.2)."""
    return f"tool:{tool_name}:{repo_id}:{_hash_args(args)}"


def query_cache_key(
    repo_id: str,
    query: str,
    history: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """`query:{repo_id}:{query_hash}` — TTL: 1h.

    ``history`` (prior conversation turns) is folded into the digest so a
    context-dependent follow-up ("who calls *it*?") never collides with the
    same query string asked single-turn. Turn order is preserved (chronological)
    while each turn's keys are sorted for stability.

    Guardrail: with no history the digest is byte-for-byte identical to the old
    single-turn key, so existing cached answers are never orphaned.
    """
    if not history:
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:32]
    else:
        canonical_history = json.dumps(
            [dict(turn) for turn in history],
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        # \x1f (unit separator) can't appear in the JSON, so the history/query
        # boundary is unambiguous.
        material = f"{canonical_history}\x1f{query}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"query:{repo_id}:{digest}"


def job_state_key(repo_id: str) -> str:
    """`job:{repo_id}` — TTL: 7 days after completion."""
    return f"job:{repo_id}"


def _hash_args(args: dict[str, Any]) -> str:
    """Canonical, sort-stable JSON hash for cache args."""
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
