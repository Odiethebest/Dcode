"""Agent service entrypoint — exposes `/healthz`, `/internal/query` (SSE),
and `/internal/tools` (manifest, debug)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from dcode_shared.db.session import SessionLocal
from dcode_shared.events import CitationEvent
from dcode_shared.internal import INTERNAL_API_KEY_HEADER
from dcode_shared.schemas import QueryRequest
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from dcode_agent import graph
from dcode_agent.settings import agent_settings
from dcode_agent.sse import SSEEmitter
from dcode_agent.state import AgentState
from dcode_agent.tools import default_registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.tool_registry = default_registry()
    app.state.compiled_graph = graph.build_graph()
    app.state.tool_cache = Redis.from_url(agent_settings.redis_url, decode_responses=True)
    app.state.db_session_factory = SessionLocal
    try:
        yield
    finally:
        close = getattr(app.state.tool_cache, "aclose", None)
        if close is not None:
            await close()


app = FastAPI(
    title="Dcode Agent",
    version="0.0.0",
    lifespan=lifespan,
)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Shallow liveness probe — does not check dependent services."""
    return {"status": "ok"}


@app.get("/internal/tools", tags=["meta"])
async def list_tools(
    x_dcode_internal_key: str | None = Header(default=None, alias=INTERNAL_API_KEY_HEADER),
) -> list[dict[str, object]]:
    """Tool manifest — used by the planner LLM and for debugging."""
    _require_internal_api_key(x_dcode_internal_key)
    registry = app.state.tool_registry
    return list(registry.manifest())


@app.post("/internal/query", tags=["agent"])
async def internal_query(
    body: QueryRequest,
    x_dcode_internal_key: str | None = Header(default=None, alias=INTERNAL_API_KEY_HEADER),
) -> StreamingResponse:
    """Run the agent for one query and stream SSE events back."""
    _require_internal_api_key(x_dcode_internal_key)
    emitter = SSEEmitter()
    state = AgentState(repo_id=str(body.repo_id), query=body.query)
    asyncio.create_task(
        _run_graph_pipeline(
            emitter,
            state,
            app.state.compiled_graph,
            app.state.tool_registry,
            app.state.tool_cache,
            app.state.db_session_factory,
        )
    )
    return StreamingResponse(
        emitter.iter_bytes(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_graph_pipeline(
    emitter: SSEEmitter,
    state: AgentState,
    compiled_graph: Any,
    tool_registry: Any,
    tool_cache: Any,
    db_session_factory: Any,
) -> None:
    """Invoke the compiled graph and flush terminal SSE events."""
    try:
        async with db_session_factory() as db:
            final_state = await compiled_graph.ainvoke(
                AgentState(
                    repo_id=state.repo_id,
                    query=state.query,
                    runtime={
                        "emitter": emitter,
                        "tool_registry": tool_registry,
                        "tool_cache": tool_cache,
                        "db": db,
                    },
                )
            )

        state_dict = _state_dict(final_state)
        citations = _citation_events(state_dict)
        for citation in citations:
            await emitter.emit_citation(
                symbol=citation.symbol,
                file_path=citation.file_path,
                line=citation.line,
                verified=citation.verified,
            )

        answer = cast(str, state_dict.get("final_answer") or state_dict.get("draft_answer") or "")
        if answer:
            await emitter.emit_partial_answer(answer)

        await emitter.emit_final_answer(
            answer=answer,
            citations=citations,
            groundedness=float(state_dict.get("groundedness_score") or 0.0),
        )
    except Exception as exc:  # noqa: BLE001 — surface any unexpected failure as SSE error
        await emitter.emit_error(code="INTERNAL", message=str(exc))
    finally:
        await emitter.close()


def _state_dict(state: Any) -> dict[str, Any]:
    if isinstance(state, dict):
        return cast(dict[str, Any], state)
    if hasattr(state, "__dict__"):
        return cast(dict[str, Any], state.__dict__)
    raise TypeError(f"unexpected graph state type: {type(state)!r}")


def _require_internal_api_key(x_dcode_internal_key: str | None) -> None:
    if x_dcode_internal_key != agent_settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "internal route requires service auth"},
        )


def _citation_events(state_dict: dict[str, Any]) -> list[CitationEvent]:
    out: list[CitationEvent] = []
    for citation in cast(list[dict[str, Any]], state_dict.get("citations", [])):
        out.append(
            CitationEvent(
                symbol=str(citation["symbol"]),
                file_path=str(citation["file_path"]),
                line=int(citation["line"]),
                verified=bool(citation["verified"]),
            )
        )
    return out
