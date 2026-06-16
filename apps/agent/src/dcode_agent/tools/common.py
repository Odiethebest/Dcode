"""Shared helpers for agent tool execution."""

from pathlib import Path
from typing import Any

import httpx
from dcode_shared.internal import internal_auth_headers

from dcode_agent.settings import agent_settings


async def fetch_internal_json(
    endpoint: str,
    repo_id: str,
    params: dict[str, str | int],
) -> Any:
    """Call the API gateway's internal retrieval routes."""
    url = f"{agent_settings.retrieval_base_url.rstrip('/')}/internal/{endpoint}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        query_params: dict[str, str | int] = {"repo_id": repo_id, **params}
        response = await client.get(
            url,
            params=query_params,
            headers=internal_auth_headers(agent_settings.internal_api_key),
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message = exc.response.text.strip() or str(exc)
        raise RuntimeError(f"internal API {endpoint} failed: {message}") from exc

    return response.json()


def repo_root(repo_id: str) -> Path:
    """Return the cloned repo root for one indexed repository."""
    root = (Path(agent_settings.workdir_base).expanduser() / repo_id).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"indexed repo workdir not found for repo_id={repo_id}")
    return root


def resolve_repo_path(repo_id: str, relative_path: str) -> Path:
    """Resolve a repo-relative path and reject traversal outside the workdir."""
    root = repo_root(repo_id)
    candidate_input = Path(relative_path)
    if candidate_input.is_absolute():
        raise ValueError("absolute paths are not allowed")

    candidate = (root / candidate_input).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("path escapes repo workdir")
    return candidate


def repo_relative_path(repo_id: str, path: Path) -> str:
    """Normalize a resolved path back to repo-relative POSIX form."""
    return path.relative_to(repo_root(repo_id)).as_posix() or "."
