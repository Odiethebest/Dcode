# Dcode Repository Structure

## Purpose

This document describes the current repository layout for developers taking over the project. It reflects the implemented codebase rather than the original skeleton.

Related documents:

- [Technical_Design.md](Technical_Design.md) for architecture and contracts;
- [Project_Plan.md](Project_Plan.md) for milestones and ownership;
- [Outstanding_Work.md](Outstanding_Work.md) for remaining work;
- [Final_Report.md](Final_Report.md) and [H1_Decision.md](H1_Decision.md) for the current evaluation snapshot.

## Root Layout

```text
Dcode/
├── packages/shared/   shared schemas, settings, DB models, SSE events, cache keys
├── apps/api/          public FastAPI gateway, repo indexing API, query SSE proxy
├── apps/worker/       RabbitMQ consumer and repository indexing pipeline
├── apps/agent/        LangGraph agent service with tools and groundedness checks
├── apps/eval/         offline evaluation harness and baseline runners
├── apps/embedding/    optional self-hosted embedding sidecar
├── apps/reranker/     optional self-hosted cross-encoder reranker sidecar
├── apps/frontend/     React/Vite UI for indexing, querying, and comparison
├── infra/             Dockerfiles, Alembic migrations, Postgres init
├── scripts/           local helper scripts
├── results/           recorded evaluation outputs
└── docs/              project design, plan, status, and decision records
```

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

`apps/frontend` is a React/Vite application with three main surfaces:

- Index: submit and monitor repositories;
- Query: ask repository questions and view citations;
- Compare: review evaluation snapshots.

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
