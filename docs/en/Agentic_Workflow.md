# Agentic AI Development Workflow

## Purpose

This project was built in an agent-assisted development environment. The team
used Claude Code, Codex, and Cursor as complementary engineering tools within
the normal review and commit process.

The workflow followed a review loop:

1. define the intended system behavior;
2. ask an agent to implement or inspect a bounded slice;
3. verify the result with local tests, live services, and repository evidence;
4. use another tool or another pass to challenge assumptions;
5. commit only the changes that survive review.

The repository history should be read with that context. AI tools contributed
drafts, edits, analysis, and debugging assistance. The team remained
responsible for scope, architecture, verification, and final commits throughout
the project.

## Tool Roles

### Claude Code

Claude Code was used mainly for broad codebase reasoning and implementation
passes. It was useful when a task required reading several files at once,
understanding a subsystem, and making a coherent multi-file change.

Typical uses:

- inspecting service boundaries before editing;
- drafting implementation changes across API, worker, agent, or frontend code;
- explaining architectural tradeoffs;
- finding stale assumptions in docs or tests;
- producing first-pass fixes that still needed local validation.

Claude Code was most useful for subsystem-level questions: what files were
connected, what assumptions were stale, and what changes needed to land
together.

### Codex

Codex was used as the local integration and verification agent. It was useful
for terminal-driven work: reading the repository, running tests, rebuilding
services, checking git history, and making small scoped changes with evidence.

Typical uses:

- running `make check`, Docker Compose builds, migrations, and live smoke tests;
- auditing whether docs matched the code;
- validating internal API contracts after retrieval / graph changes;
- re-indexing `psf/requests` with real sidecars;
- fixing agent orchestration issues exposed by live smoke tests;
- creating professional commits with focused messages.

Codex was most useful for current-state questions: whether the code worked in
the local repository, whether the services could start, and whether the tests
matched the claimed behavior.

### Cursor

Cursor was used as the interactive editor environment. It supported fast
navigation, inline code review, and small local edits while keeping the
developer close to the source files.

Typical uses:

- reading code in context while discussing changes;
- making localized edits;
- comparing nearby implementation patterns;
- keeping frontend, docs, and tests visible during review;
- manually inspecting generated diffs before commit.

Cursor was most useful for close editing: reading code in place, refining a
local change, and checking whether a diff matched nearby patterns.

## Cross-Checking Pattern

The team treated every agent output as a draft until it passed an independent
check. The common pattern was:

| Step | Primary Tool | Verification |
|---|---|---|
| Broad design or implementation draft | Claude Code or Cursor | Codex / local tests |
| Repository-wide audit | Codex | Manual review in Cursor |
| Local service integration | Codex | Docker, API smoke tests, database checks |
| Docs and report updates | Codex or Cursor | Compare against code, README, and test output |
| Final commit | Git CLI through Codex or local terminal | `git diff`, `git diff --check`, targeted tests |

This mattered because each tool had different failure modes. A model could
summarize a planned architecture that no longer matched the code. A local test
could pass while a live Docker path failed. A frontend snapshot could drift from
the recorded evaluation result. Disagreement between tools became a signal to
inspect the source of truth.

## Source-of-Truth Rules

The team followed a few practical rules:

- Code beats README claims when they disagree.
- Tests beat assumptions about behavior.
- Live smoke tests beat static inspection for service integration.
- Database state matters for retrieval work, especially embedding dimensions and
  re-indexed repo IDs.
- Generated results should not be treated as current unless they were freshly
  regenerated under the documented configuration.
- AI-written text must be edited into normal engineering prose before commit.

These rules were important in this repository. For example, the real
embedding/reranker path existed in code, but the checked-in evaluation snapshot
still came from an older state. That distinction affected README language,
`docs/en/Final_Report.md`, and the H1 decision.

## Historical Example: Retrieval and Agent Integration

A concrete example was the integration pass after the retrieval and graph stack
landed in the repository. It describes the 2026-07-27 path; the later BM25,
server-owned citation-ID, bilingual, math-rendering, and multi-turn changes are
documented in the current Technical Design and Operations runbook rather than
retroactively folded into this historical sequence.

The retrieval side added real Jina embeddings, query-side dense search, BGE
reranking, and call edges in the worker graph stage. The integration pass
verified that the agent could consume the unchanged internal API contract after
those retrieval-side changes landed.

The local smoke process was:

1. rebuild `api`, `worker`, and `agent`;
2. start the embedding and reranker host sidecars;
3. set local `.env` to Jina v2, 768 dimensions, and BGE reranker;
4. reset the old local Postgres volume because it still had `vector(1024)`;
5. migrate a fresh `vector(768)` schema;
6. re-index `psf/requests`;
7. verify `chunks=726`, `symbols=724`, `calls=303`, and `imports=65`;
8. confirm `/internal/search` returned real `dense` and `rerank` scores;
9. confirm `find_references(symbol=send)` returned real caller locations;
10. run `/api/v1/query` through the agent SSE path.

That smoke exposed an agent-side issue: `Who calls send in requests?` passed
the whole sentence as a symbol. The fix stayed within the agent planner:
extract `send` from reference-style natural language queries while preserving
the existing backtick behavior.

## How Programming Changes in the Agentic AI Era

Agentic AI changes the unit of programming work. The focus shifts from a single
edit to a short evidence loop:

1. state the intended behavior and ownership boundary;
2. let an agent search, edit, or test;
3. inspect the diff;
4. run the system;
5. decide whether the evidence is strong enough to commit.

This workflow makes boundary-setting part of the daily engineering task:

- What is the real source of truth?
- Which subsystem owns this behavior?
- What should not be changed?
- What test proves the change?
- Is this a code issue, a data issue, a stale fixture, or a documentation issue?

For Dcode, that distinction mattered. Retrieval quality, graph extraction,
agent orchestration, eval harness behavior, and frontend display were separate
ownership areas. Agentic tools were effective when those boundaries stayed
explicit.

## Practical Lessons

- Use agents for bounded tasks, not vague ownership.
- Require every non-trivial change to pass local tests.
- Use live smoke tests for service boundaries.
- Keep generated outputs and static frontend snapshots synchronized.
- Document stale assumptions immediately when they are found.
- Do not let AI style leak into project documentation; keep prose direct and
  technical.
- Prefer small commits with clear messages over large mixed changes.

The most productive pattern was: AI proposes, another tool or test challenges,
and the engineer decides what is safe to commit.
