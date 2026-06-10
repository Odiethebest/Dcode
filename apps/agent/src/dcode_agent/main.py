"""Agent service entrypoint — exposes `/healthz`, `/internal/query` (SSE),
and `/internal/tools` (manifest, debug).

The API gateway proxies all public `/api/v1/query` traffic here. We keep
agent endpoints under `internal/*` to make the trust boundary explicit
and to allow direct curl testing during development.

Skeleton: `/internal/query` schedules `_run_stub_pipeline()` instead of
the real LangGraph (graph.build_graph()) so the SSE wire format is
exercised end-to-end without LLM calls. Real ReAct loop lands at M2.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dcode_shared.schemas import QueryRequest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from dcode_agent.sse import SSEEmitter
from dcode_agent.state import AgentState
from dcode_agent.tools import default_registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.tool_registry = default_registry()
    # TODO(M2): app.state.compiled_graph = graph.build_graph()
    # TODO(M2): warm DB / Redis pools per DESIGN.md §2.6.
    yield


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
async def list_tools() -> list[dict[str, object]]:
    """Tool manifest — used by the planner LLM and for debugging."""
    registry = app.state.tool_registry
    return list(registry.manifest())


@app.post("/internal/query", tags=["agent"])
async def internal_query(body: QueryRequest) -> StreamingResponse:
    """Run the agent for one query and stream SSE events back.

    Wire format follows DESIGN.md §4.3 exactly (event names + payload shapes
    defined in `dcode_shared.events`).
    """
    emitter = SSEEmitter()
    state = AgentState(repo_id=str(body.repo_id), query=body.query)
    asyncio.create_task(_run_stub_pipeline(emitter, state))
    return StreamingResponse(
        emitter.iter_bytes(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_stub_pipeline(emitter: SSEEmitter, state: AgentState) -> None:
    """Skeleton substitute for `graph.build_graph().ainvoke(state)`.

    Emits one thought + one final_answer so the SSE protocol is exercised
    end-to-end. Replaced by the real LangGraph invocation at M2.
    """
    try:
        await emitter.emit_thought(
            step=1,
            content="(skeleton) Agent received query; real ReAct loop lands at M2.",
        )
        await emitter.emit_final_answer(
            answer=f"(skeleton) Stub answer for: {state.query}",
            citations=[],
            groundedness=1.0,
        )
    except Exception as exc:  # noqa: BLE001 — surface any unexpected failure as SSE error
        await emitter.emit_error(code="INTERNAL", message=str(exc))
    finally:
        await emitter.close()
