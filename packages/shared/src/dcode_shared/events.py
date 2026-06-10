"""SSE event types — implements DESIGN.md §4.3 Agent SSE Output Format.

Event names are fixed (`thought`, `tool_call`, `tool_result`, `citation`,
`partial_answer`, `final_answer`, `error`). Payload shapes are typed below.
The encoder helper emits the wire format used over `text/event-stream`.
"""

from typing import Any, Literal

from pydantic import BaseModel

EventName = Literal[
    "thought",
    "tool_call",
    "tool_result",
    "citation",
    "partial_answer",
    "final_answer",
    "error",
]


class ThoughtEvent(BaseModel):
    step: int
    content: str


class ToolCallEvent(BaseModel):
    step: int
    tool: str
    args: dict[str, Any]


class ToolResultEvent(BaseModel):
    step: int
    tool: str
    result_summary: str


class CitationEvent(BaseModel):
    symbol: str
    file_path: str
    line: int
    verified: bool


class PartialAnswerEvent(BaseModel):
    delta: str


class FinalAnswerEvent(BaseModel):
    answer: str
    citations: list[CitationEvent]
    groundedness: float


class ErrorEvent(BaseModel):
    code: str
    message: str


def sse_encode(event: EventName, data: BaseModel) -> bytes:
    """Encode a typed event to the SSE wire format (UTF-8 bytes)."""
    payload = data.model_dump_json()
    return f"event: {event}\ndata: {payload}\n\n".encode()
