# Dcode Repository Structure

## Purpose

This document describes the current repository layout for developers taking over the project. It reflects the implemented codebase rather than the original skeleton.

Related documents:

- [Technical_Design.md](Technical_Design.md) for architecture and contracts;
- [Project_Plan.md](Project_Plan.md) for milestones and ownership;
- [Outstanding_Work.md](Outstanding_Work.md) for remaining work;
- [Final_Report.md](Final_Report.md) for the current evaluation snapshot and H1 decision.

## Root Layout

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

Only three markdown files sit at the top level: `README.md` (the front door),
`CLAUDE.md` (agent session notes), and this repository's `LICENSE`. Everything
else documentation-shaped lives under `docs/`, with historical records —
the development-era problem register, its changelog, and the executed frontend
redesign brief — under `docs/archive/`.

The public entry point is `apps/api`. The frontend uses only `/api/v1/*`; internal retrieval, graph, and agent routes are not public surfaces.

## Shared Package

`packages/shared` is the cross-service contract layer.

| Path | Role |
|---|---|
| `schemas.py` | Pydantic API schemas and enums |
| `events.py` | Typed SSE payloads and encoding helper |
| `cache.py` | Redis key builders |
| `settings.py` | Shared runtime configuration |
| `embedding.py` | Stub and HTTP embedding clients |
| `reranker.py` | Identity and HTTP reranker clients |
| `internal.py` | Internal API key dependency helper |
| `db/models.py` | SQLAlchemy models |
| `db/session.py` | Async engine and session factory |

## API Service

`apps/api` is the public FastAPI service.

| Path | Role |
|---|---|
| `main.py` | App setup, health endpoint, CORS, router registration |
| `deps.py` | DB, Redis, RabbitMQ, and agent client dependencies |
| `routes/repos.py` | Repository submission and status reads |
| `routes/query.py` | Public query SSE proxy |
| `routes/internal.py` | Internal retrieval and graph lookup routes |
| `tests/` | Public route, internal route, and SSE tests |

## Worker Service

`apps/worker` consumes indexing jobs and builds the index.

| Path | Role |
|---|---|
| `main.py` | RabbitMQ consumer loop |
| `pipeline.py` | Monotonic indexing state machine |
| `context.py` | Pipeline context shared across stages |
| `stages/clone.py` | Git clone stage |
| `stages/parse.py` | Python AST parsing |
| `stages/chunk.py` | AST-boundary chunk creation |
| `stages/embed.py` | Embedding cache and persistence |
| `stages/graph.py` | Symbol table and graph edge extraction |

## Agent Service

`apps/agent` streams answer generation through a bounded LangGraph loop.

| Path | Role |
|---|---|
| `main.py` | Internal agent service routes |
| `graph.py` | Planning, tool execution, synthesis, groundedness loop |
| `state.py` | Agent state and step cap |
| `sse.py` | SSE event emitter |
| `groundedness.py` | Citation verification |
| `tools/` | Registered agent tools |

## Evaluation

`apps/eval` contains the offline evaluation harness, question fixtures, baseline runners, and metric calculation code. Recorded outputs live under `results/`.

The current checked-in results are useful as a snapshot, but real sidecar mode should be re-indexed and rerun before making new H1 claims.

## Frontend

`apps/frontend` is a React 18 + TypeScript (strict) + Vite + Tailwind SPA, around
2k lines, with four routes:

| Route | Surface |
|---|---|
| `/workbench` | The product. Topbar repo switcher, a conversational thread driven by the live SSE stream, and a code + call-graph inspector. Clicking a citation opens the real indexed source at the cited line; call-graph neighbours are clickable, so exploration chains through the graph. |
| `/` | Marketing landing. |
| `/methodology` | The evaluation story for reviewers, read from the generated snapshot. |
| `/preview` | Design-system gallery — every shared primitive in every state. |

An earlier IA had one tab per endpoint (`Index` / `Query` / `Compare`); it was
retired, because it exposed the API's shape rather than the user's task — nobody
hand-copies a repository UUID between pages.

| Path | Role |
|---|---|
| `src/api/client.ts` | The only module that talks to the gateway |
| `src/api/types.ts` | Hand-mirrored copy of the `dcode_shared` schemas |
| `src/components/ui/` | Six shared primitives, consuming design tokens only |
| `src/components/workbench/` | Thread, trace, inspector, switcher, history rail |
| `src/hooks/useThread.ts` | Conversation state; derives each turn's state from arrived events |
| `src/demo/evalSnapshot.ts` | **Generated** from `results/eval-real/` — do not edit |
| `tests/` | Includes guardrail tests pinning the rules in [Honesty_Constraints.md](Honesty_Constraints.md) |

## Infrastructure

| Path | Role |
|---|---|
| `docker-compose.yml` | Local development stack |
| `docker-compose.prod.yml` | Production-shaped stack |
| `infra/alembic/` | Database migrations |
| `infra/docker/` | Service Dockerfiles |
| `.env.example` | Local environment template |
| `.env.production.example` | Production environment template |

## Current Boundaries

- Python is the only indexed language.
- Stub embedding and reranker modes remain the default local configuration.
- Real sidecars require explicit environment variables and a compatible database vector dimension.
- Graph v1 is best-effort and does not fully model dynamic Python behavior.
- The current agent planner and synthesis path are rule-based.
