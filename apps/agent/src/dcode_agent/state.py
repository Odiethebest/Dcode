"""Per-request LangGraph state for the Dcode agent.

A single AgentState dataclass flows through every node. Each tool_call
appends a step; the ReAct loop terminates when step_count reaches the
configured ``AgentSettings.max_steps`` cap or when the planner emits a
synthesize decision.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from dcode_shared.graph_tools import GRAPH_TOOLS

AgentMode = Literal["full", "agent_no_graph", "hybrid_only", "dense_only"]

SearchMode = Literal["hybrid", "dense", "sparse"]

# One agent, one synthesis prompt, one citation protocol, one guardrail — the
# evaluation arms differ only in these two dimensions. Keeping the mapping in
# one table is what lets the harness claim the arms are comparable; a mode whose
# retrieval or expansion is decided somewhere else would silently break that.
#
# ``retrieval`` reaches /internal/search. It must also travel in the tool's
# args, not just here: the tool cache key is derived from (tool, repo_id, args),
# so an arm-level retrieval mode kept out of the args would make B2's dense
# search and B3's hybrid search collide on one cache entry.
#
# ``expansion`` gates follow-up tools after the first retrieval:
#   none   — answer from the first search alone
#   local  — read_file / get_file_outline: more of the same files, no graph
#   full   — the graph and reference tools as well
_MODE_TABLE: dict[str, tuple[SearchMode, Literal["none", "local", "full"]]] = {
    # B4 — the system under test.
    "full": ("hybrid", "full"),
    # B3.5 — diagnostic. Identical to B4 except the graph is switched off, so
    # (B4 - B3.5) isolates the call graph while (B4 - B3) measures the whole
    # agent. Diagnostic only: it is not part of the H1 pass criteria.
    "agent_no_graph": ("hybrid", "local"),
    # B3 — hybrid retrieval, no tool expansion at all.
    "hybrid_only": ("hybrid", "none"),
    # B2 — vanilla dense RAG, sharing B4's synthesis and guardrail so its
    # groundedness is measured rather than a template constant.
    "dense_only": ("dense", "none"),
}

# Tools that consult the graph or the reference index. `local` expansion may not
# use these; that exclusion is the entire definition of the B3.5 arm.
#
# The set itself lives in `dcode_shared.graph_tools` because the evaluation
# harness has to answer the same question — "did the graph do this?" — when it
# counts graph-sourced ground-truth hits. The two lists had drifted apart in both
# directions; that module records what each omission cost.
#
# Deliberately absent: `get_file_outline` and `read_file`. B3.5 keeps both. They
# read more of a file the arm already retrieved, which is the agent loop, not the
# graph, and a no-graph arm denied them would inflate `B4 - B3.5`.
STRUCTURAL_TOOLS = GRAPH_TOOLS


def search_mode_for(mode: AgentMode) -> SearchMode:
    return _MODE_TABLE[mode][0]


def expansion_for(mode: AgentMode) -> Literal["none", "local", "full"]:
    return _MODE_TABLE[mode][1]


@dataclass
class AgentState:
    """In-flight state carried through the LangGraph nodes."""

    repo_id: str
    query: str
    # Which evaluation arm this request is. Every mode shares the synthesis
    # model, prompt, citation protocol and groundedness guardrail; only
    # retrieval and tool expansion differ. See ``_MODE_TABLE``.
    mode: AgentMode = "full"
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
    evidence_catalog: dict[str, Any] | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    groundedness_score: float | None = None
    final_answer: str | None = None
    error: str | None = None
    # The repository's corpus generation, read once per query and folded into
    # every tool cache key. `None` means it could not be read, and the tool
    # cache is bypassed for the request rather than shared with another
    # generation — see `_index_revision` in graph.py.
    index_revision: int | None = None
    runtime: dict[str, Any] = field(default_factory=dict, repr=False)
