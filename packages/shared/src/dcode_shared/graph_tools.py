"""Which agent tools consult the call graph. One definition, two consumers.

Two places have to answer "did the graph do this?" and they were answering
differently:

- ``dcode_agent.state`` decides which tools the ``agent_no_graph`` arm (B3.5) may
  **not** use. Removing exactly these tools is the entire definition of that arm,
  and ``B4 - B3.5`` is therefore the measured contribution of the graph.
- ``dcode_eval.run`` decides which citation origins count toward
  ``new_gt_hits_from_graph_evidence`` — the per-question count of ground-truth
  hits the graph found that retrieval had not.

Both are measuring the same thing, so a name in one list and not the other makes
the two disagree about the size of the effect the whole project is testing. They
did disagree, in both directions:

**``get_file_outline`` was counted as graph evidence but is not disabled for
B3.5.** It lists the symbols defined in a file; it walks no edges. Because the
no-graph arm keeps it, every hit it produced was credited to the graph by the
counter while the ablation correctly credited it to the agent loop.

There is a one-line proof that the old set could not have been measuring the
graph, and it is checkable against committed bytes. Recompute
``results/eval-h1-repeat3-2026-07-31/`` both ways:

===========  ==========================  ========================
arm          old set (incl. outline)     this set
===========  ==========================  ========================
``B3.5``     12 hits, all three repeats  **0**, all three repeats
``B4``       14 / 12 / 16                4 / 3 / 5
===========  ==========================  ========================

``B3.5`` **is** B4 with the graph switched off. An arm with no graph tools has no
graph contribution by construction, so its only correct value is zero — and the
old set scored it 12, against 14 for the arm that does have a graph. A measure
that cannot separate those two is not measuring the graph. On B4 the same set
read 3.5x this one; that ratio is the visible symptom, the ``B3.5`` row is the
reason.

Verified live, not only by recomputation: a fresh ``B3.5``/``B4`` run on the same
index after this change reported 0 graph hits for ``B3.5`` and 3 for ``B4``, with
every counted chunk carrying a graph origin.

**``find_call_path`` is a graph tool and was in neither list.** Walking a chain
of ``calls`` edges from one symbol to another is the most purely graph-dependent
thing the agent does. Its omission from the eval set undercounted the graph
(harmlessly on the recorded run — every one of its ground-truth hits was also
surfaced by another counted tool — but not by design). Its omission from the
agent set was latent rather than active: the planner reaches it only through a
branch already gated on the arm's expansion policy, so B3.5 never received it.
A latent hole in a guard is still a hole.

The rule: a tool belongs here if answering with it requires reading ``edges`` or
the symbol index for something other than the file you are already looking at.
Reading more of a file you already retrieved is the agent loop, not the graph.
"""

GRAPH_TOOLS = frozenset(
    {
        "find_call_path",
        "find_definition",
        "find_references",
        "get_call_neighbors",
        "get_dependencies",
        "get_dependents",
    }
)
