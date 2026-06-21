"""Baseline B0 — GitHub Search (pure keyword).

Industry-standard control: queries the public GitHub code search API.
Requires GITHUB_TOKEN env var for authenticated requests (higher rate limit).
"""

import re
import uuid
from urllib.parse import urlparse

import httpx
from dcode_shared.schemas import Chunk, ScoreComponents

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.baselines.common import template_answer
from dcode_eval.settings import eval_settings


def _parse_github_repo(url: str) -> str | None:
    """Extract 'owner/repo' from a GitHub URL. Returns None if not a GitHub URL."""
    scp = re.match(r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?$", url)
    if scp:
        return scp.group(1)
    parsed = urlparse(url)
    if parsed.hostname in ("github.com", "www.github.com"):
        path = parsed.path.lstrip("/").removesuffix(".git")
        parts = path.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return None


async def _fetch_repo_url(repo_id: str) -> str | None:
    """Look up the original repo URL from the API status endpoint."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        response = await client.get(
            f"{eval_settings.api_base_url.rstrip('/')}/api/v1/repos/{repo_id}/status",
        )
        if response.status_code != 200:
            return None
        data = response.json()
        url = data.get("url", "")
        return url if url else None


def _query_to_keywords(query: str, max_words: int = 6) -> str:
    """Extract keywords from a natural language query for GitHub code search."""
    import re
    # Strip punctuation, keep backtick-quoted symbols as-is
    symbols = re.findall(r"`([^`]+)`", query)
    words = re.sub(r"[^\w\s]", " ", query).split()
    stopwords = {"what", "where", "how", "does", "is", "the", "a", "an", "in", "to",
                 "of", "for", "and", "or", "do", "does", "from", "with", "this"}
    keywords = [w for w in words if w.lower() not in stopwords]
    combined = symbols + [w for w in keywords if w not in symbols]
    return " ".join(combined[:max_words])


async def _github_search(query: str, repo_slug: str, k: int, token: str | None) -> list[dict]:
    """Call GitHub code search API and return raw items.

    GitHub Search allows 30 req/min (authenticated). We sleep 2s between calls
    to stay safely under the limit when running a multi-question eval suite.
    """
    import asyncio

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    keywords = _query_to_keywords(query)
    params = {"q": f"{keywords} repo:{repo_slug}", "per_page": min(k, 30)}
    await asyncio.sleep(2)  # stay under 30 req/min rate limit
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        response = await client.get(
            "https://api.github.com/search/code",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response.json().get("items", [])


def _item_to_chunk(item: dict, rank: int) -> Chunk:
    """Convert a GitHub Search result item to a Chunk."""
    file_path = item.get("path", "")
    name = item.get("name", "")
    score = 1.0 / (rank + 1)
    return Chunk(
        chunk_id=uuid.uuid4(),
        file_path=file_path,
        symbol_name=name,
        start_line=1,
        end_line=1,
        content=item.get("url", ""),
        score=score,
        score_components=ScoreComponents(dense=0.0, sparse=score, rerank=score),
    )


class GithubSearchBaseline(Baseline):
    id = "B0"
    description = "GitHub code search — pure keyword (DESIGN.md §2.4.3)."

    def __init__(self, github_token: str | None = None) -> None:
        import os
        self._token = github_token or os.environ.get("GITHUB_TOKEN")

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        repo_url = await _fetch_repo_url(repo_id)
        if not repo_url:
            return []
        repo_slug = _parse_github_repo(repo_url)
        if not repo_slug:
            return []
        items = await _github_search(query, repo_slug, k, self._token)
        return [_item_to_chunk(item, rank) for rank, item in enumerate(items)]

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        chunks = await self.retrieve(repo_id, query, 5)
        return template_answer("B0 GitHub Search", chunks)
