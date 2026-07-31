"""Per-request LangGraph state for the Dcode agent.

A single AgentState dataclass flows through every node. Each tool_call
appends a step; the ReAct loop terminates when step_count reaches the
configured ``AgentSettings.max_steps`` cap or when the planner emits a
synthesize decision.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """In-flight state carried through the LangGraph nodes."""

    repo_id: str
    query: str
    # Prior conversation turns (bounded by the gateway) + the original follow-up
    # text preserved when the contextualize node rewrites `query` for retrieval.
    history: list[dict[str, str]] = field(default_factory=list)
    raw_query: str | None = None
    step_count: int = 0
    thoughts: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    pending_tool_name: str | None = None
    pending_tool_args: dict[str, Any] = field(default_factory=dict)
    draft_answer: str | None = None
    # ``None`` means template/legacy citation parsing. A dict (including an
    # empty one) means LLM synthesis used the server-owned ``[C#]`` protocol.
    evidence_catalog: dict[str, str] | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    groundedness_score: float | None = None
    final_answer: str | None = None
    error: str | None = None
    runtime: dict[str, Any] = field(default_factory=dict, repr=False)
