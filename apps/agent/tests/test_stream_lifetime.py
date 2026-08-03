"""Stream keep-alive and the whole-request ceiling (Deploy.md R-2).

Both exist because of one platform fact: a request that transfers no data for
five minutes is closed, and even with data it is capped at about fifteen. The
agent previously had per-hop timeouts only, so a query could outlive both and
the reader would see a stream that simply stopped.
"""

import asyncio

import pytest
from dcode_agent.sse import SSEEmitter


async def _drain(emitter: SSEEmitter, *, heartbeat_seconds: float) -> list[bytes]:
    return [chunk async for chunk in emitter.iter_bytes(heartbeat_seconds=heartbeat_seconds)]


async def test_no_heartbeat_when_disabled() -> None:
    """Zero keeps the original behaviour, so nothing changes where it is not wanted."""
    emitter = SSEEmitter()
    await emitter.emit_thought(1, "hello")
    await emitter.close()

    chunks = await _drain(emitter, heartbeat_seconds=0)

    assert len(chunks) == 1
    assert b"thought" in chunks[0]
    assert not any(chunk.startswith(b":") for chunk in chunks)


async def test_a_quiet_stream_emits_comment_frames() -> None:
    emitter = SSEEmitter()

    async def finish_later() -> None:
        await asyncio.sleep(0.25)
        await emitter.emit_thought(1, "finally")
        await emitter.close()

    task = asyncio.create_task(finish_later())
    chunks = await _drain(emitter, heartbeat_seconds=0.05)
    await task

    heartbeats = [chunk for chunk in chunks if chunk.startswith(b":")]
    assert heartbeats, "a stream quiet for longer than the interval must be kept alive"
    assert all(chunk == b": keep-alive\n\n" for chunk in heartbeats)
    assert b"thought" in chunks[-1]


async def test_heartbeats_are_sse_comments_the_client_already_skips() -> None:
    """A `:`-prefixed line is a comment in the SSE grammar.

    The frontend parser drops those already (src/api/client.ts), so this adds
    no event type and changes no client contract. If the frame ever stops
    starting with ':' it becomes an unparseable event instead.
    """
    emitter = SSEEmitter()
    await emitter.close()
    assert b": keep-alive\n\n".startswith(b":")
    assert (await _drain(emitter, heartbeat_seconds=10)) == []


async def test_heartbeat_does_not_swallow_the_end_of_stream() -> None:
    """close() must still terminate while the heartbeat loop is running."""
    emitter = SSEEmitter()
    await emitter.emit_partial_answer("x")
    await emitter.close()

    chunks = await asyncio.wait_for(_drain(emitter, heartbeat_seconds=0.01), timeout=2.0)

    assert b"partial_answer" in chunks[0]


@pytest.mark.parametrize("budget", [0.05])
async def test_the_request_budget_emits_a_labelled_error(budget: float) -> None:
    """A query that overruns says so, rather than the connection just ending.

    TIMEOUT is distinct from INTERNAL because "this took too long" is a
    different thing for a reader to know than "something broke". Nothing
    half-finished is emitted: a partial walk has not been through the
    groundedness verifier, and presenting it would claim a check that never
    ran (Honesty_Constraints §3).
    """
    from dcode_agent import main as agent_main
    from dcode_agent.settings import agent_settings
    from dcode_agent.state import AgentState

    class _NeverFinishes:
        async def ainvoke(self, _state: object) -> object:
            await asyncio.sleep(30)
            raise AssertionError("should have been cancelled")

    class _Session:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            return None

    original = agent_settings.request_budget_seconds
    agent_settings.request_budget_seconds = budget
    try:
        emitter = SSEEmitter()
        await agent_main._run_graph_pipeline(
            emitter,
            AgentState(repo_id="r", query="q", mode="full", history=[]),
            _NeverFinishes(),
            None,
            None,
            _Session,
            None,
        )
        chunks = await _drain(emitter, heartbeat_seconds=0)
    finally:
        agent_settings.request_budget_seconds = original

    body = b"".join(chunks)
    assert b"event: error" in body
    assert b"TIMEOUT" in body
    assert b"final_answer" not in body
