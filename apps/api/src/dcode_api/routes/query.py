"""Query endpoint — implements DESIGN.md §4.3 Agent SSE Output Format.

Architecture: the API gateway proxies POST /api/v1/query to the Agent
service's /internal/query, streaming SSE events back unchanged. This keeps
the agent fully isolated and lets it be scaled / replaced independently.

Skeleton: if the agent service is unreachable, emit one stub `thought` event
plus an `error` event so the SSE protocol is still exercised end-to-end.
"""

from collections.abc import AsyncIterator

import httpx
from dcode_shared.events import ErrorEvent, ThoughtEvent, sse_encode
from dcode_shared.schemas import QueryRequest
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from dcode_api.deps import get_agent_client

router = APIRouter(tags=["query"])


@router.post("/query")
async def query(
    body: QueryRequest,
    agent: httpx.AsyncClient = Depends(get_agent_client),
) -> StreamingResponse:
    """Stream SSE events from the agent service back to the client.

    TODO(M2): wire query cache check (DESIGN.md §3.3 `query:{repo_id}:{hash}`)
    before forwarding to the agent.
    """
    return StreamingResponse(
        _proxy_to_agent(agent, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )


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
        # Skeleton fallback: emit one stub thought so the SSE protocol is
        # still exercised end-to-end when the agent service is offline.
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
