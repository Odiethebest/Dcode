# Dcode Technical Design

## Document Scope

This document is the technical authority for Dcode. It describes the system architecture, service boundaries, data model, API contracts, non-functional requirements, technology choices, and implementation decisions that guide the codebase.

For execution planning, ownership, milestones, and risks, see [Project_Plan.md](Project_Plan.md). For the project overview and setup instructions, see [README.md](../../README.md).

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
roughly 2k lines, with four routes:

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
| `src/demo/evalSnapshot.ts` | **Generated** from `results/eval-real/` — do not edit |
| `tests/` | Includes guardrail tests pinning the rules in [Honesty_Constraints.md](Honesty_Constraints.md) |

## Runtime Architecture

The deployed local stack contains the following services:

| Service | Responsibility |
|---|---|
| API | Public FastAPI gateway for repository submission, status reads, query SSE, and internal retrieval routes |
| Worker | RabbitMQ consumer that clones repositories, parses Python code, chunks files, writes embeddings, and builds graph edges |
| Agent | Internal LangGraph service that plans tool calls, executes retrieval and graph tools, synthesizes answers, and verifies citations |
| Frontend | React/Vite UI for indexing, querying, and comparing evaluation results |
| Embedding sidecar | Optional self-hosted HTTP embedding model service |
| Reranker sidecar | Optional self-hosted HTTP cross-encoder reranker service |
| Postgres | Durable repository, chunk, symbol, and edge storage with pgvector |
| Redis | Query cache, tool cache, and job state cache |
| RabbitMQ | Durable indexing job queue |

The API is the only public backend entry point. The frontend talks to `/api/v1/*`. The agent, retrieval, graph, and database surfaces remain internal and are protected by an internal API key.

## Data Model

The authoritative schema is the Alembic migration under `infra/alembic/`; the
SQLAlchemy models in `packages/shared/src/dcode_shared/db/models.py` mirror it.
This section covers the shape and the reasoning, not the DDL.

### Storage topology

| Store | Role | Durable? |
|---|---|---|
| **PostgreSQL 15 + pgvector** | `repos`, `chunks`, `symbols`, `edges` — vectors *and* graph in one instance | Yes (`postgres_data` volume) |
| **Redis 7** | Embedding cache, tool cache, query-SSE cache, live job-state snapshot | No — cache, TTL per key |
| **RabbitMQ** | Durable indexing job queue (`dcode.index_jobs`) — transport, not storage | Message-durable |
| **Repo workdir volume** | Cloned repository source on disk, read by the agent's filesystem tools | Yes (`repo_workdirs`) |

**Why vectors and the graph share one PostgreSQL instance** rather than adding a
dedicated vector service: one connection pool, one backup boundary, and one
consistency model. A citation's chunk and its graph neighbours are read in the
same transaction, so the inspector cannot show source from one snapshot and
edges from another. The cost is that vector search is bounded by what pgvector
does, which at this corpus size is not the constraint.

Redis holds only derived state. Losing it costs cache warmth and the live
per-stage progress snapshot; nothing authoritative. That is why indexing status
merges a durable Postgres row with an optional Redis overlay.

### Tables

| Table | Purpose |
|---|---|
| `repos` | Repository metadata, indexing status, progress, and failure state |
| `chunks` | Code and documentation chunks, sparse `tsv`, and dense embedding vectors |
| `symbols` | Module, class, function, and method definitions extracted from Python AST |
| `edges` | Static relationships such as imports, calls, inheritance, and references |

`chunks` carries both retrieval surfaces on the same row — an HNSW index on
`embedding` for dense search and a GIN index on `tsv` for full-text — so hybrid
retrieval fuses two rankings over one table rather than joining two stores.
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
4. Write sparse text vectors and dense embeddings.
5. Extract symbols and graph edges.
6. Mark the repository ready for search and agent queries.

The default local environment uses stub embeddings and an identity-compatible reranker. Real retrieval quality requires the embedding and reranker sidecars described in [Operations.md](Operations.md).

## Retrieval Design

The internal search API combines sparse and dense retrieval:

- sparse retrieval uses PostgreSQL full-text search;
- dense retrieval uses pgvector similarity search when real embeddings are available;
- hybrid ranking combines sparse and dense candidates;
- reranking can call the BGE reranker sidecar;
- `score_components` exposes sparse, dense, and rerank components when those paths are active.

The route contract is intentionally stable so the agent and evaluation harness can consume the same internal API in stub and real-model modes.

## Graph Design

The graph stage currently extracts:

- module symbols;
- class symbols;
- function and method symbols;
- internal module import edges;
- best-effort intra-repository call edges.

Graph v1 is intentionally conservative. It may miss dynamic calls, complex attribute chains, and mixin or MRO-based `self.method` references. Those gaps are graph coverage limits, not API contract breaks.

## Agent Design

The agent is a bounded LangGraph loop with rule-based planning. It can call registered tools for search, definitions, references, dependencies, dependents, file context, and repository status.

The answer path is:

1. classify the query intent;
2. choose one or more tools;
3. execute internal API calls;
4. synthesize a response from tool results — a rule-based template by default, or an optional LLM (`SYNTHESIS_MODEL`) that streams a grounded, citation-formatted answer;
5. verify citations against indexed evidence;
6. stream typed SSE events through the API gateway.

Groundedness is a hard product requirement. Unsupported citations must be removed or flagged instead of being presented as verified evidence.

## API Contracts

The public API includes:

| Route | Purpose |
|---|---|
| `POST /api/v1/repos` | Submit a GitHub repository for indexing |
| `GET /api/v1/repos/{repo_id}/status` | Read indexing status and progress |
| `POST /api/v1/query` | Stream an agent answer over SSE |

The internal API includes:

| Route | Purpose |
|---|---|
| `/internal/search` | Hybrid retrieval over indexed chunks |
| `/internal/find_definition` | Locate symbol definitions |
| `/internal/find_references` | Locate callers or references |
| `/internal/get_dependencies` | Outgoing graph dependencies (what a module imports) |
| `/internal/get_dependents` | Incoming graph dependents (what imports a module) |
| `/internal/get_file_outline` | File-level symbol outline |

Internal routes are shared by agent tools and evaluation baselines. Route names, schemas, and error semantics should not be changed without updating all consumers.

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
