"""LangGraph state for the Dcode agent — implements DESIGN.md §2.3.3.

A single AgentState dataclass flows through every node. Each tool_call
appends a step; the ReAct loop terminates when step_count >= MAX_STEPS
(hard cap per §2.3.1) or when the planner emits a synthesize decision.
"""

from dataclasses import dataclass, field
from typing import Any

MAX_STEPS = 8  # DESIGN.md §2.3.1 — single-query upper bound (forces synthesize)


@dataclass
class AgentState:
    """In-flight state carried through the LangGraph nodes."""

    repo_id: str
    query: str
    step_count: int = 0
    thoughts: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    pending_tool_name: str | None = None
    pending_tool_args: dict[str, Any] = field(default_factory=dict)
    draft_answer: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    groundedness_score: float | None = None
    final_answer: str | None = None
    error: str | None = None
    runtime: dict[str, Any] = field(default_factory=dict, repr=False)
