"""SSE producer for the agent service.

Wraps the typed events in `dcode_shared.events` with a small in-memory
asyncio.Queue producer. Nodes in the LangGraph state machine push events;
the FastAPI handler drains them as bytes via `iter_bytes()`.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from dcode_shared.events import (
    CitationEvent,
    ErrorEvent,
    FinalAnswerEvent,
    PartialAnswerEvent,
    ThoughtEvent,
    ToolCallEvent,
    ToolResultEvent,
    sse_encode,
)


class SSEEmitter:
    """Producer-side of a one-shot SSE event stream."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def emit_thought(self, step: int, content: str) -> None:
        await self._queue.put(
            sse_encode("thought", ThoughtEvent(step=step, content=content))
        )

    async def emit_tool_call(self, step: int, tool: str, args: dict[str, Any]) -> None:
        await self._queue.put(
            sse_encode("tool_call", ToolCallEvent(step=step, tool=tool, args=args))
        )

    async def emit_tool_result(self, step: int, tool: str, result_summary: str) -> None:
        await self._queue.put(
            sse_encode(
                "tool_result",
                ToolResultEvent(step=step, tool=tool, result_summary=result_summary),
            )
        )

    async def emit_citation(
        self, symbol: str, file_path: str, line: int, verified: bool
    ) -> None:
        await self._queue.put(
            sse_encode(
                "citation",
                CitationEvent(symbol=symbol, file_path=file_path, line=line, verified=verified),
            )
        )

    async def emit_partial_answer(self, delta: str) -> None:
        await self._queue.put(
            sse_encode("partial_answer", PartialAnswerEvent(delta=delta))
        )

    async def emit_final_answer(
        self, answer: str, citations: list[CitationEvent], groundedness: float
    ) -> None:
        await self._queue.put(
            sse_encode(
                "final_answer",
                FinalAnswerEvent(
                    answer=answer, citations=citations, groundedness=groundedness
                ),
            )
        )

    async def emit_error(self, code: str, message: str) -> None:
        await self._queue.put(
            sse_encode("error", ErrorEvent(code=code, message=message))
        )

    async def close(self) -> None:
        """Signal end-of-stream; iter_bytes() will exit on the next loop."""
        await self._queue.put(None)

    async def iter_bytes(self) -> AsyncIterator[bytes]:
        """Drain the queue. Caller streams these bytes to the client."""
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk
