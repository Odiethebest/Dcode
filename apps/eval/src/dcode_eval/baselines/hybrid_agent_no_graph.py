"""Baseline B3.5 — the full agent with the call graph switched off.

Diagnostic arm, deliberately outside the H1 pass criteria.

The 2026-07-31 run showed B4 beating B3 on cross-file questions while the graph
itself contributed only 4 new ground-truth hits across 3 of 33 questions. Two
explanations fit that: the graph is doing a little, or the agent's multi-step
evidence selection is doing most of it and would work about as well without a
graph at all. `B4 - B3` cannot tell them apart because B3 takes no follow-up
steps whatsoever.

This arm holds the agent, prompt, model, citation protocol, groundedness
guardrail, step budget, and hybrid retrieval identical to B4, and removes only
`find_definition`, `find_references`, `get_call_neighbors`, `get_dependencies`
and `get_dependents`. `read_file` and `get_file_outline` stay, because an agent
without a graph is still allowed to read the code it retrieved. So:

    B4 - B3     the whole agent system
    B4 - B3.5   the call graph on its own
    B3.5 - B3   multi-step reading, no graph

Keeping `read_file` and the outline tool matters for honesty in a specific
direction: a weakened B3.5 would inflate `B4 - B3.5` and make the graph look
better than it is.
"""

from dcode_shared.schemas import Chunk

from dcode_eval.baselines import common
from dcode_eval.baselines.base import AnswerResult, Baseline


class HybridAgentNoGraphBaseline(Baseline):
    id = "B3.5"
    description = "Hybrid retrieval + the shared Agent loop, call-graph tools disabled."

    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        # Identical to B3 and B4's starting retrieval by construction.
        return await common.internal_search(repo_id, query, k, mode="hybrid")

    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        return await common.stream_agent_no_graph_answer(repo_id, query)
