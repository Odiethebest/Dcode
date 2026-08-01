# Dcode Technical Design

## Document Scope

This document is the technical authority for Dcode. It describes the system architecture, service boundaries, data model, API contracts, non-functional requirements, technology choices, and implementation decisions that guide the codebase.

For the project overview and the recorded evaluation result, see the [root README](../../README.md); for the H1 verdict and outstanding work, [Final_Report.md](Final_Report.md); for running the stack, [Operations.md](Operations.md).

## System Overview

Dcode is a structure-aware code understanding platform for repository onboarding. It indexes a GitHub repository into two complementary retrieval surfaces:

- semantic chunks for sparse and dense code retrieval;
- a static graph of symbols, imports, and best-effort call edges.

An agent consumes those surfaces through internal APIs and streams grounded answers through the public API gateway. Every answer is expected to include code citations that can be checked against indexed repository evidence.

## Repository Layout

```text
Dcode/
├── README.md          entry point: hypothesis, architecture, recorded result, how to run
├── CLAUDE.md          operational notes for agent sessions (tooling config, not project docs)
├── Makefile           developer commands — `make help` lists them
├── packages/shared/   shared schemas, settings, DB models, SSE events, cache keys
├── apps/api/          public FastAPI gateway, repo indexing API, query SSE proxy
├── apps/worker/       RabbitMQ consumer and repository indexing pipeline
├── apps/agent/        LangGraph agent service with tools and groundedness checks
├── apps/eval/         offline evaluation harness and baseline runners
├── apps/embedding/    self-hosted embedding sidecar
├── apps/reranker/     self-hosted cross-encoder reranker sidecar
├── apps/frontend/     React/Vite SPA — landing, workbench, methodology
├── design/            the two HTML prototypes the UI was built from (see design/README.md)
├── infra/             Dockerfiles, Alembic migrations, Postgres init
├── scripts/           helper scripts, incl. sync_eval_artifacts.py
├── results/           recorded evaluation runs (see results/README.md for which is current)
└── docs/              project documentation; docs/archive/ holds development-era records
```

`apps/api` is the only public entry point. The frontend calls `/api/v1/*`
exclusively; internal retrieval, graph, and agent routes are not public surfaces.

### Frontend surfaces

`apps/frontend` is a React 18 + TypeScript (strict) + Vite + Tailwind SPA of
roughly 4.2k TypeScript/TSX lines, with four routes:

| Route | Surface |
|---|---|
| `/workbench` | The product. Topbar repo switcher, a conversational thread driven by the live SSE stream, and a code + call-graph inspector. Clicking a citation opens the real indexed source at the cited line; call-graph neighbours are clickable, so exploration chains through the graph. |
| `/` | Marketing landing. |
| `/methodology` | The evaluation story for reviewers, read from the generated snapshot. |
| `/preview` | Design-system gallery — every shared primitive in every state. |

An earlier information architecture had one tab per endpoint (`Index` / `Query` /
`Compare`). It was retired because it exposed the API's shape rather than the
user's task — nobody hand-copies a repository UUID between pages.

| Path | Role |
|---|---|
| `src/api/client.ts` | The only module that talks to the gateway |
| `src/api/types.ts` | Hand-mirrored copy of the `dcode_shared` schemas |
| `src/components/ui/` | Six shared primitives, consuming design tokens only |
| `src/components/workbench/` | Thread, trace, inspector, switcher, history rail |
| `src/hooks/useThread.ts` | Conversation state; derives each turn's state from arrived events |
| `src/demo/evalSnapshot.ts` | **Generated** from `results/eval-h1-repeat3-2026-07-31/` — do not edit |
| `tests/` | Includes guardrail tests pinning the rules in [Honesty_Constraints.md](Honesty_Constraints.md) |

## Runtime Architecture

The deployed local stack contains the following services:

| Service | Responsibility |
|---|---|
| API | Public FastAPI gateway for repository submission, status reads, query SSE, and internal retrieval routes |
| Worker | RabbitMQ consumer that clones repositories, parses Python code, chunks files, writes embeddings, and builds graph edges |
| Agent | Internal LangGraph service that plans tool calls, executes retrieval and graph tools, synthesizes answers, and verifies citations |
| Frontend | React/Vite landing, exploration workbench, generated methodology view, and component preview |
| Embedding sidecar | Optional self-hosted HTTP embedding model service |
| Reranker sidecar | Optional self-hosted HTTP cross-encoder reranker service |
| Postgres | Durable repository, chunk, symbol, and edge storage with pgvector |
| Redis | Query cache, tool cache, and job state cache |
| RabbitMQ | Durable indexing job queue |

The API is the only public backend entry point. The frontend talks to `/api/v1/*`. The agent, retrieval, graph, and database surfaces remain internal and are protected by an internal API key.

## Data Model

The authoritative schema is the Alembic migration chain under
`infra/migrations/`. The SQLAlchemy models in
`packages/shared/src/dcode_shared/db/models.py` cover the four tables used by the
current runtime, but they do **not** mirror every migration object:
migration-managed indexes and the unfinished `index_runs` provenance integration
are absent from the ORM. This section covers the shape and the reasoning, not the
DDL.

### Storage topology

| Store | Role | Durable? |
|---|---|---|
| **PostgreSQL 15 + pgvector** | Runtime tables `repos`, `chunks`, `symbols`, `edges`, plus the currently runtime-unintegrated `index_runs` provenance table | Yes (`postgres_data` volume) |
| **Redis 7** | Embedding cache, tool cache, query-SSE cache, live job-state snapshot | No — cache, TTL per key |
| **RabbitMQ** | Durable indexing job queue (`dcode.index_jobs`) — transport, not storage | Message-durable |
| **Repo workdir volume** | Cloned repository source on disk, read by the agent's filesystem tools | Yes (`repo_workdirs`) |

**Why vectors and the graph share one PostgreSQL instance** rather than adding a
dedicated vector service: one connection pool and one backup boundary. This does
not make a whole index generation atomic. The embed stage commits `chunks`
before the graph stage separately commits `symbols` and `edges`, while source
and graph-neighbour inspector calls are separate requests. A failure between
stages can therefore expose new chunks beside stale or missing graph rows until
the next successful re-index. The cost is custom consistency handling, and
vector search remains bounded by what pgvector does.

Redis holds only derived state. Losing it costs cache warmth and the live
per-stage progress snapshot; nothing authoritative. That is why indexing status
merges a durable Postgres row with an optional Redis overlay.

### Tables

| Table | Purpose |
|---|---|
| `repos` | Repository metadata, indexing status, progress, failure state, and `index_revision` |
| `chunks` | Code and documentation chunks plus dense embedding vectors |
| `symbols` | Module, class, function, and method definitions extracted from Python AST |
| `edges` | Static relationships such as imports, calls, inheritance, and references |
| `index_runs` | Append-only provenance records introduced by migration; the current worker and ORM do not populate or expose them yet |

`repos.current_index_run_id` is likewise present in the migration schema but is
not wired into the current runtime. Existing indexes continue to use
`repos.commit_sha` and `index_revision`; no documentation or UI should imply
that an executor-backed provenance record exists for a completed index today.

Dense retrieval uses the HNSW index on `chunks.embedding`. Sparse retrieval
builds an application-side Okapi BM25 corpus from each chunk's symbol, path,
signature, and content. That immutable corpus is cached by
`(repo_id, index_revision)`; replacing a repository's chunks increments the
revision in the same transaction, so an API process cannot silently reuse the
previous generation. The older `tsv` column and GIN index remain dormant.
`edges` is indexed in both directions (`source_id` and `target_id`), which is what
makes reverse lookups such as *who calls this?* a single indexed query.

Important constraints:

- all user-facing data is scoped by `repo_id`;
- `chunks.embedding` is fixed by `EMBEDDING_DIM` at migration time;
- switching from stub vectors to Jina v2 768-dimensional embeddings requires a fresh database volume or a compatible migration;
- graph edges are best-effort and should be treated as static analysis evidence, not a complete runtime call trace.

## Indexing Pipeline

The worker pipeline is a monotonic state machine:

```text
queued -> cloning -> parsing -> embedding -> graphing -> ready
```

Any failed stage moves the repository to `failed` with an error reason. The pipeline stages are:

1. Clone the target repository with a shallow git checkout.
2. Discover Python files and parse them with the standard library `ast` module.
3. Build chunks at module, class, function, and method boundaries.
4. Replace the repository's chunks and dense embeddings, incrementing its
   retrieval-corpus revision.
5. Extract symbols and graph edges.
6. Mark the repository ready for search and agent queries.

The default local environment uses stub embeddings and an identity-compatible reranker. Real retrieval quality requires the embedding and reranker sidecars described in [Operations.md](Operations.md).

## Retrieval Design

The internal search API combines sparse and dense retrieval:

- sparse retrieval uses standard Okapi BM25 with corpus-wide IDF, term-frequency
  saturation, length normalization, and a versioned source-code tokenizer;
- dense retrieval uses pgvector similarity search when real embeddings are available;
- hybrid ranking combines sparse and dense candidates with weighted reciprocal
  rank fusion (`k=60`, dense weight `2.0`, sparse weight `1.0` by default);
- reranking can call the BGE reranker sidecar;
- `score_components` exposes sparse, dense, and rerank components when those paths are active.

BM25 treats `symbol_name`, `file_path`, `signature`, and `content` as one
unweighted document. Its tokenizer keeps the compact identifier and also splits
snake_case and camelCase, so exact names and their component words share one
ranking model. The fixed methodology parameters are `k1=1.2` and `b=0.75`;
evaluation artifacts record those values and the tokenizer version.

The route contract is intentionally stable so the agent and evaluation harness can consume the same internal API in stub and real-model modes.

## Graph Design

The graph stage currently extracts:

- module symbols;
- class symbols;
- function and method symbols;
- internal module import edges;
- best-effort intra-repository call edges.

Graph v1 is intentionally conservative. It may miss dynamic calls, complex attribute chains, and mixin or MRO-based `self.method` references. Those gaps are graph coverage limits, not API contract breaks.

`get_call_neighbors` supplements resolved graph edges with call expressions read
from the indexed source. A source call whose static target cannot be resolved is
returned explicitly as `unresolved_target` rather than silently discarded.
Caller/callee intent routing recognises both English and Chinese question forms;
the graph data and limitations remain the same in either language.

## Agent Design

The agent is a bounded LangGraph loop with rule-based planning. Its eleven
registered tools (`dcode_agent.tools.default_registry`) are `search_code`,
`read_file`, `find_definition`, `find_references`, `find_call_path`,
`get_call_neighbors`, `get_dependencies`, `get_dependents`, `get_file_outline`,
`grep`, and `list_directory`.

The answer path is:

1. contextualize a follow-up from the bounded client history, with a narrow
   deterministic symbol-binding fallback for caller/callee pronouns;
2. classify the query intent;
3. choose one or more tools;
4. execute internal API calls;
5. synthesize a response from tool results — a rule-based template by default,
   or an optional LLM (`SYNTHESIS_MODEL`) that cites request-local server-owned
   evidence IDs such as `[C1]`;
6. verify citations against indexed evidence;
7. stream typed SSE events through the API gateway.

Groundedness is a hard product requirement. The server resolves LLM evidence IDs back to indexed locations or symbols before verification; ordinary backticked code is formatting, not a citation. Unsupported IDs and explicit file-line citations must be removed or flagged instead of being presented as verified evidence.

LLM synthesis follows the natural language of the current question rather than
the source code or prior turns. Chinese questions receive Chinese answers and
English questions receive English answers; code identifiers stay verbatim.
Math uses Markdown `$...$` / `$$...$$` delimiters and is rendered by the
frontend through KaTeX, which also normalizes common LaTeX delimiters outside
code spans and fences.

## API Contracts

The public API includes:

| Route | Purpose |
|---|---|
| `POST /api/v1/repos` | Submit a GitHub repository for indexing |
| `GET /api/v1/repos/{repo_id}/status` | Read indexing status and progress |
| `POST /api/v1/query` | Stream an agent answer over SSE |
| `GET /api/v1/repos/{repo_id}/source` | Resolve indexed source for a citation, with explicit degradation when that granularity is unavailable |
| `GET /api/v1/repos/{repo_id}/neighbors` | Resolve caller, callee, and reference neighbours for a symbol |

`POST /api/v1/query` accepts `repo_id`, `query`, and optional client-supplied
`history` turns (`role` + `content`). The gateway keeps the most recent history
within configurable budgets (defaults: 6 turns, 2,000 total characters, 4,000
characters per turn), incorporates the bounded history into the query-cache key,
and proxies it to the agent. The API and agent remain stateless between requests.

The internal API includes:

| Route | Purpose |
|---|---|
| `/internal/search` | Hybrid retrieval over indexed chunks |
| `/internal/get_chunks` | Fetch indexed chunks by id, so graph results can carry their source into the answer prompt |
| `/internal/find_definition` | Locate symbol definitions |
| `/internal/find_references` | Locate callers or references |
| `/internal/find_call_path` | Shortest chain of `calls` edges between two symbols, bounded by `max_depth` |
| `/internal/get_call_neighbors` | Return resolved callers/callees plus source call expressions with explicit unresolved targets |
| `/internal/get_dependencies` | Outgoing graph dependencies (what a module imports) |
| `/internal/get_dependents` | Incoming graph dependents (what imports a module) |
| `/internal/get_file_outline` | File-level symbol outline |

Internal routes are shared by agent tools and evaluation baselines. Route names, schemas, and error semantics should not be changed without updating all consumers.

## Evaluation Design

### Question set construction

The versioned question set lives at
`apps/eval/src/dcode_eval/questions/data/questions.jsonl`. The current
`psf/requests` set contains 33 reviewed questions — 5 single-file L1, 16
cross-file L2, and 12 architecture-level L3 — assembled from 16 manually written
questions (`source: manual`) and a 17-question expansion reverse-constructed
from this corpus's indexed call relationships (`source: graph_reverse`). Ground
truth uses stable `file_path + symbol_name + start_line` anchors which the
harness resolves against the selected `--repo-id`; recorded chunk UUIDs are
retained only for backwards compatibility with archived runs. The file is frozen
per run by sha256 in the run's `provenance.json`.

The target remains 50–80 reviewed questions. Two properties of the current set
keep it from serving as a general benchmark, and both are recorded rather than
corrected: a suite reverse-constructed from the system's own graph output cannot
contain a flow that graph misses, which favours B4; and three pre-existing L2/L3
pairs share ground truth, so the two levels the H1 rule conjoins are not
independent samples. It is one repository, and it generalises to nothing.

### Baseline and result contract

The harness exposes six baseline tiers:

| Baseline | Current meaning |
|---|---|
| B0 | External code search; requires a provider token. Measured 2026-07-31 at **file level only** (`results/eval-b0-2026-07-31/`) — it returns a path and no line, so it has no chunk-level result and stays outside the H1 decision. Its figures query a live external index and cannot be regenerated from committed bytes |
| B1 | Application-side Okapi BM25 over the complete chunk corpus. Retrieval reference, template answer, **not in the H1 decision** |
| B2 | Dense-only retrieval through the shared Agent path (`dense_only`) |
| B3 | Weighted BM25 + dense RRF and reranking, then the shared Agent path with no tool expansion (`hybrid_only`) |
| B3.5 | B4 with the graph and reference tools disabled (`agent_no_graph`). **Diagnostic only**, reported beside the decision, never inside it |
| B4 | The same hybrid start and Agent path, plus bounded graph/structure expansion (`full`) |

Every arm from B2 up shares one synthesis model, prompt, citation protocol,
groundedness verifier and step budget. They differ only along two axes, and the
mapping lives in one table (`dcode_agent.state._MODE_TABLE`) so the claim that
the arms are comparable is checkable in one place:

| Mode | Retrieval | Tool expansion |
|---|---|---|
| `dense_only` | dense | none |
| `hybrid_only` | hybrid | none |
| `agent_no_graph` | hybrid | `read_file`, `get_file_outline` |
| `full` | hybrid | all tools |

Retrieval mode is a `search_code` **tool argument**, not ambient request state,
because the tool cache key is `(tool, repo_id, args)` — a mode held outside the
args would let a dense and a hybrid search for the same query collide on one
cache entry and make two arms silently identical.

The current `results/eval-h1-repeat3-2026-07-31/` snapshot exercises
`okapi_bm25_v1` in B1 and in the sparse component of B3/B4, over the 33-question
suite. `results/eval-h1-bm25-2026-07-30/` is the superseded previous complete
run, and `results/eval-real/` before it used the legacy lexical heuristic; both
remain available as historical snapshots.

B0 and B1 answer from a template, so their groundedness is the constant `1.0`
and they emit no citation events; they are retrieval references outside the H1
decision. B2 was in that position until the `dense_only` agent mode gave it the
same synthesis path, citation protocol and verifier as B4 — every arm in the
decision now exercises the real verifier. Groundedness is also no longer one of
the composite terms; see the H1 decision section below.

Each run records `run_config.json`, suite metrics, taxonomy breakdowns, and
per-question rows. A complete suite also writes `h1_report.json`. New BM25 runs
record the formula, tokenizer, document fields, `k1`, `b`, and corpus revision,
and reject the result if that revision changes during execution.

The scoring protocol is `uniform_final_verified_evidence_v2`. Each question
records three auditable views: the initial candidate list, the verified final
evidence list, and the list used for the official metric. **The official list is
the ordered verified final evidence for every agent arm — B2, B3, B3.5 and B4
alike.** B0/B1 emit no citations and stay on candidate top-`k`, outside the
decision. Structural origins are retained so a row can show whether a new
ground-truth hit came from a graph or outline tool. All three metrics see at most
the first `k` IDs, including MRR; the complete final-evidence list is retained
separately for audit.

`v1` applied the final-evidence rule to B4 only and left the other arms on
top-`k`. That asymmetry decided the 2026-07-31 `L3` result — +0.045 mixed against
+0.051 symmetric, across a 0.05 bar — which is why the rule is now uniform rather
than resolved in whichever direction happened to be convenient.

### H1 decision and additional gates

The executable `h1_report` decision compares B4 with B2 and B3 on L2 and L3.
For each level it computes the mean of **Recall@k, MRR and nDCG@k**; H1 is
`supported` only if B4 exceeds **both** baselines by at least `0.05` composite
points on **both** levels.

Groundedness was a fourth term until 2026-07-31. It is 1.000 for every arm in
every recorded run, so it added no discrimination — but because it is identical
across arms, removing it multiplies every margin by 4/3, which is arithmetically
the same as lowering the threshold to `0.0375`. **It was removed after four runs
had missed the four-term bar.** Every `h1_report.json` carries the four-term
reading under `four_term` for exactly this reason. Full disclosure in
[Final_Report.md](Final_Report.md).

Two additional product-quality gates are reported separately from that
executable decision:

- pairwise win rate against B2 should exceed 60%, but the judge is currently a
  stub and the metric is unmeasured;
- programmatic groundedness should reach 95%; the current B4 run clears that
  guardrail.

The committed `results/eval-h1-repeat3-2026-07-31/` snapshot counts the graph's
contribution two independent ways: per question through
`new_gt_hits_from_structural_evidence`, and at the level of the decision through
the `B3.5` ablation under `h1_report.json` → `diagnostics`. Both say the same
thing — the effect is real, consistent, and small. The verdict stays
`unsupported`; the margins are in the generated verdict table in
[Final_Report.md](Final_Report.md), which reads them straight from
`h1_report.json`.

**Two properties of that decision a reader has to know.** The first is that the
deciding margin is smaller than its own spread across three identical repeats,
one of which returned `supported` on its own — so the verdict is reported with
that spread beside it rather than as a settled quantity. The second is that
`B4 - B3` moves when either the graph or the agent's multi-step reading moves,
which is why `B3.5` exists; it is a diagnostic and is deliberately excluded from
the pass criteria, because adding an arm to the decision rule would be changing
the pass criteria. The asymmetric-scoring caveat that used to sit here is
resolved: under `uniform_final_verified_evidence_v2` every agent arm is scored by
one rule, and `candidate_*` remains recorded per question so the other scoring
stays auditable without being selectable after the fact.

## Non-Functional Requirements

| Area | Requirement |
|---|---|
| Reproducibility | Evaluation runs must record model configuration, repo commit, question set, and output directory |
| Groundedness | Final answers should cite indexed evidence and satisfy the project groundedness threshold |
| Isolation | All repository data must be scoped by `repo_id` |
| Local usability | `make check`, `make smoke`, and Docker Compose should be sufficient for local validation |
| Security | Repository URLs must reject localhost and private IP targets |
| Degradation | Stub model mode must keep the stack usable for development and tests |

## Technology Choices

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy async |
| Agent | LangGraph with bounded rule-based planning |
| Database | PostgreSQL 15 with pgvector |
| Queue | RabbitMQ |
| Cache | Redis |
| Frontend | React, TypeScript, Vite |
| Tooling | uv, pytest, ruff, mypy, Docker Compose |
| Embeddings | Jina v2 code embedding sidecar for real retrieval mode |
| Reranking | BGE reranker v2 m3 sidecar for real reranking mode |

## Open Limits

- Full inheritance and richer reference edges remain follow-up graph work.
- The evaluation suite needs a larger question set and independent baseline retrieval paths.
- Answer synthesis can run through an optional LLM (`SYNTHESIS_MODEL`, default `stub`); the planner remains rule-based.
- Production deployment still depends on DNS and runtime environment decisions.

Any implementation change that affects these contracts should update this document and the matching execution notes.
