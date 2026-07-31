"""Baseline B0 — GitHub Search (pure keyword).

Industry-standard control: queries the public GitHub code search API.

**B0 retrieves files, not symbols.** The API returns a path, a matched fragment
and character offsets *within that fragment* — verified against a live response,
there is no line number anywhere in it. So B0 has no chunk-level result to give,
and it is scored on the file-level metrics the harness computes for every arm.
Its chunk-level cells stay empty rather than being filled by a mapping we
invented, which would credit the baseline with a precision it does not have.

**Its numbers cannot be regenerated from committed bytes.** Every other figure
in this project can. This one queries a live external index that re-ranks and
re-crawls, so re-running it is a fresh measurement, not a reproduction. It is a
retrieval reference and is not part of the H1 decision.

`GITHUB_TOKEN` raises the rate limit; public-repo search needs no scopes. With
no token the baseline reports **unmeasured** rather than returning nothing,
because an empty result scores zero and a zero is a claim about GitHub Search.
"""

import re
import uuid
from urllib.parse import urlparse

import httpx
from dcode_shared.schemas import Chunk, ScoreComponents

from dcode_eval.baselines.base import AnswerResult, Baseline
from dcode_eval.baselines.common import template_answer
from dcode_eval.settings import eval_settings

# Stable per-path ids, so repeated runs of an unreproducible baseline at least
# produce diff-able artifacts.
_B0_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

# GitHub's code search endpoint allows 10 requests/minute when authenticated.
_SECONDS_BETWEEN_CALLS = 7.0


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
                 "of", "for", "and", "or", "do", "from", "with", "this"}
    keywords = [w for w in words if w.lower() not in stopwords]
    combined = symbols + [w for w in keywords if w not in symbols]
    return " ".join(combined[:max_words])


async def _github_search(
    query: str,
    repo_slug: str,
    k: int,
    token: str | None,
) -> list[dict[str, object]]:
    """Call GitHub code search API and return raw items.

    The *code search* endpoint is limited to 10 requests/minute authenticated —
    not the 30/min that applies to the rest of the Search API, which an earlier
    version of this comment assumed. At 2s between calls a 33-question suite
    trips 403 partway through and the remaining questions score zero, which
    would look like a baseline result rather than a rate limit.
    """
    import asyncio

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    keywords = _query_to_keywords(query)
    params: dict[str, str | int] = {
        "q": f"{keywords} repo:{repo_slug}",
        "per_page": min(k, 30),
    }
    await asyncio.sleep(_SECONDS_BETWEEN_CALLS)
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        response = await client.get(
            "https://api.github.com/search/code",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]


def _item_to_chunk(item: dict[str, object], rank: int) -> Chunk:
    """Convert a GitHub Search result item to a Chunk.

    `chunk_id` is a deterministic UUID5 of the repo-relative path, not a random
    UUID. A random one can never equal a ground-truth chunk id, so every
    chunk-level metric was structurally pinned at 0.000 no matter how good the
    result was — a fabricated failure wearing the shape of a measurement.

    A stable id per file cannot match ground truth either, and is not meant to:
    B0 is scored on the file-level metrics. What it buys is that two runs
    returning the same file produce the same id, so the artifacts are
    diff-able and the emptiness is visibly deliberate.
    """
    file_path = str(item.get("path", ""))
    name = str(item.get("name", ""))
    score = 1.0 / (rank + 1)
    return Chunk(
        chunk_id=uuid.uuid5(_B0_NAMESPACE, file_path),
        file_path=file_path,
        symbol_name=name,
        start_line=1,
        end_line=1,
        content=str(item.get("url", "")),
        score=score,
        score_components=ScoreComponents(dense=0.0, sparse=score, rerank=score),
    )


class MissingGithubTokenError(RuntimeError):
    """Raised instead of silently scoring zero when B0 cannot be measured."""


class GithubSearchBaseline(Baseline):
    id = "B0"
    description = "GitHub code search — external pure-keyword baseline."

    def __init__(self, github_token: str | None = None) -> None:
        import os

        self._token = github_token or os.environ.get("GITHUB_TOKEN") or None

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        if self._token is None:
            # Returning [] here would record 0.000 across the board, which reads
            # as "GitHub Search found nothing" rather than "we did not run it".
            # Unmeasured is a blank; zero is a claim.
            raise MissingGithubTokenError(
                "B0 needs GITHUB_TOKEN to query the code search API. Without it "
                "the baseline is unmeasured; it must not be recorded as zero."
            )
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
