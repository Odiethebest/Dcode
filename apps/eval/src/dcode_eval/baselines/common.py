"""Shared HTTP helpers for baseline implementations."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from dcode_shared.schemas import Chunk

from dcode_eval.baselines.base import AnswerResult
from dcode_eval.settings import eval_settings


async def internal_search(repo_id: str, query: str, k: int) -> list[Chunk]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        response = await client.get(
            f"{eval_settings.api_base_url.rstrip('/')}/internal/search",
            params={"repo_id": repo_id, "query": query, "k": k},
        )
    response.raise_for_status()
    return [Chunk.model_validate(item) for item in response.json()]


def template_answer(label: str, chunks: list[Chunk], *, max_chunks: int = 3) -> AnswerResult:
    if not chunks:
        return AnswerResult(answer=f"{label}: no retrieved chunks.", citations=[], groundedness=0.0)

    lines = [f"{label} top evidence:"]
    citations: list[str] = []
    for chunk in chunks[:max_chunks]:
        citation = f"`{chunk.file_path}:{chunk.start_line}`"
        citations.append(citation)
        lines.append(f"- {citation} `{chunk.symbol_name}`")
    return AnswerResult(answer="\n".join(lines), citations=citations, groundedness=0.0)


async def stream_full_system_answer(repo_id: str, query: str) -> AnswerResult:
    answer = ""
    citations: list[str] = []
    groundedness = 0.0
    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client,
        client.stream(
            "POST",
            f"{eval_settings.api_base_url.rstrip('/')}/api/v1/query",
            json={"repo_id": repo_id, "query": query},
        ) as response,
    ):
        response.raise_for_status()
        async for event, payload in parse_sse(response.aiter_lines()):
            if event == "citation":
                citations.append(f"`{payload['file_path']}:{payload['line']}`")
            elif event == "final_answer":
                answer = str(payload["answer"])
                groundedness = float(payload["groundedness"])
    return AnswerResult(answer=answer, citations=citations, groundedness=groundedness)


async def parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    event_name: str | None = None
    data_lines: list[str] = []
    async for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if event_name is not None and data_lines:
                yield event_name, json.loads("\n".join(data_lines))
            event_name = None
            data_lines = []
            continue
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ").strip()
        elif line.startswith("data: "):
            data_lines.append(line.removeprefix("data: ").strip())
