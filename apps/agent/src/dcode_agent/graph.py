"""LangGraph state machine — implements DESIGN.md §2.3.3.

Node topology:
  plan → tool_call → (decide) → [continue → plan] | [synthesize → groundedness_check → END]

Skeleton: each node raises NotImplementedError. The FastAPI handler in
main.py uses `stub_pipeline()` to demonstrate the SSE wire format
without making real LLM calls. The real ReAct loop is wired at M2.
"""

from typing import Any

from langgraph.graph import END, StateGraph

from dcode_agent.state import MAX_STEPS, AgentState

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def plan_node(state: AgentState) -> AgentState:
    """Decide next tool to call (or signal synthesize).

    TODO(M2): call planner LLM with current observations + tool manifest.
    """
    raise NotImplementedError("plan node — implement per DESIGN.md §2.3 at M2")


async def tool_call_node(state: AgentState) -> AgentState:
    """Execute the chosen tool via the registry (with cache check).

    TODO(M2): look up tool by name; check Redis tool: cache (D-2.3.2);
    on miss, call execute(); store result in observations; increment step.
    """
    raise NotImplementedError("tool_call node — implement per DESIGN.md §2.3.2 at M2")


async def synthesize_node(state: AgentState) -> AgentState:
    """Compose a final answer from observations + citations.

    TODO(M2): call synthesis LLM with structured observations to produce
    `draft_answer` + tentative citation list.
    """
    raise NotImplementedError("synthesize node — implement per DESIGN.md §2.3.3 at M2")


async def groundedness_node(state: AgentState) -> AgentState:
    """Verify every citation per D-2.3.1; flag or strip unverified.

    TODO(M2): call groundedness.verify(state.draft_answer, state.repo_id, db);
    set state.final_answer and state.groundedness_score.
    """
    raise NotImplementedError("groundedness node — implement per DESIGN.md §2.3.4 at M2")


# ---------------------------------------------------------------------------
# Edge logic
# ---------------------------------------------------------------------------


def decide_next(state: AgentState) -> str:
    """Continue the ReAct loop, or stop and synthesize."""
    if state.step_count >= MAX_STEPS:
        return "synthesize"  # forced synthesis at the §2.3.1 cap
    if state.draft_answer is not None:
        return "synthesize"
    return "plan"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph() -> Any:
    """Compile the LangGraph state machine for an agent invocation.

    TODO(M2): wire checkpointer + observability hooks per DESIGN.md NFR-5.
    """
    g = StateGraph(AgentState)
    g.add_node("plan", plan_node)
    g.add_node("tool_call", tool_call_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("groundedness_check", groundedness_node)

    g.set_entry_point("plan")
    g.add_edge("plan", "tool_call")
    g.add_conditional_edges(
        "tool_call",
        decide_next,
        {"plan": "plan", "synthesize": "synthesize"},
    )
    g.add_edge("synthesize", "groundedness_check")
    g.add_edge("groundedness_check", END)

    return g.compile()
