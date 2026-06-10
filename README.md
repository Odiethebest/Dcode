# Dcode: Structure-Aware Code Understanding Platform

> A retrieval platform for codebase onboarding — pairing semantic vector indexing with a static call graph, queried through a multi-tool ReAct agent that returns programmatically verified citations.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-state%20machine-FF6F00)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%20+%20pgvector-4169E1?logo=postgresql)](https://github.com/pgvector/pgvector)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Core Hypothesis](#core-hypothesis-h1)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Evaluation Protocol](#evaluation-protocol)
- [Key Design Decisions](#key-design-decisions)
- [Technical Design](docs/DESIGN.md)
- [Project Plan](docs/PLAN.md)
- [Outstanding Work (TODO)](docs/TODO.md)
- [Repository Structure](docs/Structure.md)
- [Team](#team)

---

## Overview

When a new engineer joins a mature codebase, the questions they ask are *relational*, not *similarity-based*: "how is auth implemented end-to-end?", "what depends on this module?", "who calls this function?". Today's mainstream tools answer the wrong question:

| Tool category | Representative | Limitation |
|---|---|---|
| Keyword search | GitHub Search, ripgrep | Literal match only; no semantic intent |
| Flat vector RAG | Standard RAG implementations | Text similarity only; loses call relationships |
| General chat assistants | Generic LLM apps | No grounded codebase context; citation hallucination |

Dcode is a structure-aware retrieval platform. It asynchronously builds a dual index — semantic vectors and a static call graph — and exposes it through a multi-tool ReAct agent. Every code reference in a final answer is verified against the index before reaching the user.

### What it handles

| Concern | Mechanism |
|---|---|
| Async indexing | Job queue + worker with monotonic state machine (`queued → cloning → parsing → embedding → graphing → ready`) |
| Chunk granularity | AST-level chunks via tree-sitter (no fixed-window sliding) |
| Call graph | jedi-derived definitions / references / dependencies |
| Hybrid retrieval | Dense (pgvector) + sparse (BM25) → RRF fusion → cross-encoder rerank |
| Multi-hop reasoning | LangGraph state machine, 8 tools, ≤ 8 steps per query |
| Hallucination control | Programmatic groundedness check, ≥ 95% hard constraint (non-disableable) |
| Reproducible evaluation | Five-tier baseline ladder + L1/L2/L3 question taxonomy |
| Multi-tenancy | All chunks / symbols / jobs isolated by `repo_id` |

---

## Core Hypothesis (H1)

> **On cross-file and architecture-level code understanding tasks, the combination of structure-aware indexing (semantic vectors + a code call graph) with multi-tool agent orchestration achieves significant and reproducible improvements over flat vector RAG and keyword search baselines — measured by standard IR metrics and end-to-end answer quality.**

The project's entire engineering investment serves this **falsifiable** hypothesis. If acceptance metrics in the [evaluation protocol](#evaluation-protocol) are not met, H1 is recorded as unsupported. No threshold tuning, no patches.

---

## Architecture

```
       ┌──────────┐  HTTPS/SSE   ┌──────────────────┐
       │  Client  │ ───────────▶ │ FastAPI Gateway  │
       └──────────┘              └────┬─────────┬───┘
                                      │         │
                       POST /repos    │         │  POST /query (SSE)
                                      ▼         ▼
                               ┌──────────┐   ┌──────────────────┐
                               │  Queue   │   │  LangGraph Agent │
                               │ RabbitMQ │   └────┬─────────────┘
                               └────┬─────┘        │ tool calls
                                    ▼              ▼
                              ┌──────────┐  ┌──────────────────┐
                              │  Worker  │  │ Retrieval & Graph│
                              │ AST/jedi │  │ hybrid + graph   │
                              └────┬─────┘  └────┬─────────────┘
                                   │ write       │ read
                                   ▼             ▼
                              ┌──────────────────────────────┐
                              │ PostgreSQL + pgvector + Redis│
                              └──────────────────────────────┘
```

**Components**

- **API Gateway** (FastAPI) — auth, multi-tenant routing, SSE termination
- **Index Worker** — `clone → tree-sitter AST chunk → embed → jedi graph → persist`
- **Agent Orchestrator** — LangGraph state machine with 8 tools and a groundedness guardrail
- **Retrieval Layer** — hybrid search + atomic graph queries (`find_definition`, `find_references`, `get_dependencies`, `get_file_outline`)
- **Storage** — PostgreSQL + pgvector (single store for vectors and graph), Redis for embedding / tool-result / query caches
- **Evaluation Harness** (offline) — five-tier baseline runner with stratified metrics

**Infrastructure**

- **Database**: PostgreSQL 15 with the pgvector extension (HNSW on `embedding`, GIN on `tsv`)
- **ORM / Migrations**: SQLAlchemy 2.0 async + Alembic
- **Queue**: RabbitMQ with `aio-pika` client
- **Python workspace**: `uv` workspaces (5 members) + Hatch backend
- **Frontend**: React 18 + TypeScript (strict) + Vite + Tailwind + TanStack Query
- **Apps**: FastAPI gateway + worker + standalone agent service + frontend, orchestrated by Docker Compose
- **Deployment target**: `dcode.odieyang.com`

Full architecture, component design, and design decisions: [`docs/DESIGN.md`](docs/DESIGN.md).

---

## Data Model

Four core tables, all isolated by `repo_id` for multi-tenancy. Vectors and call graph live in the same PostgreSQL instance, eliminating a separate vector service.

### Entity Hierarchy

```
repos (1) ──── (N) chunks
   │
   └── (1) ──── (N) symbols ──── (M) edges
                     │
                     └── (linked) chunks
```

### Schema Highlights

```sql
-- Chunks: AST-level slices, vector and tsvector colocated for hybrid retrieval
CREATE TABLE chunks (
    id          UUID PRIMARY KEY,
    repo_id     UUID REFERENCES repos(id),
    file_path   TEXT NOT NULL,
    chunk_type  chunk_type,        -- function / method / class / module_doc
    symbol_name TEXT,
    start_line  INT, end_line INT,
    imports     JSONB,
    content     TEXT,
    embedding   VECTOR(N),         -- N from EMBEDDING_DIM env var
    tsv         TSVECTOR           -- BM25 / full-text
);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING gin (tsv);

-- Symbols + edges form the call graph
CREATE TABLE edges (
    id          UUID PRIMARY KEY,
    repo_id     UUID,
    source_id   UUID REFERENCES symbols(id),
    target_id   UUID REFERENCES symbols(id),
    edge_type   edge_type,         -- calls / imports / inherits / references
    source_line INT
);
CREATE INDEX ON edges (repo_id, source_id, edge_type);
CREATE INDEX ON edges (repo_id, target_id, edge_type);  -- reverse lookups
```

Full schema, indexes, and Redis key naming conventions: [`docs/DESIGN.md` §3](docs/DESIGN.md).

---

## API Reference

### Indexing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/repos` | Submit a repo URL for indexing — returns `202 Accepted` with `repo_id` |
| `GET`  | `/api/v1/repos/{repo_id}/status` | Index progress and per-stage status |

```http
POST /api/v1/repos
Content-Type: application/json

{ "url": "https://github.com/psf/requests.git" }
```

```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{ "repo_id": "uuid", "status": "queued" }
```

### Query

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/query` | Ask a natural-language question — server-sent event stream |

```http
POST /api/v1/query
Content-Type: application/json
Accept: text/event-stream

{
  "repo_id": "uuid",
  "query": "How is authentication wired end-to-end?"
}
```

**SSE event types** (fixed payload schema):

| Event | Payload |
|---|---|
| `thought` | Agent reasoning step |
| `tool_call` | Tool invocation with args |
| `tool_result` | Tool return summary |
| `citation` | Verified code reference with `verified: true/false` |
| `partial_answer` | Streamed answer delta |
| `final_answer` | Complete answer + citations + groundedness score |
| `error` | Failure code + message |

Full request / response contracts and error semantics: [`docs/DESIGN.md` §4](docs/DESIGN.md).

---

## Getting Started

> **Status**: M0 skeleton complete (2026-06-10). All 7 services boot healthy via
> `docker compose up`, `make check` is green (ruff + mypy --strict + pytest + eslint +
> tsc + vitest), and the schema is applied. The Worker stages, Agent LangGraph nodes,
> and Retrieval Layer return stub responses — real behavior lands at M1 / M2.
> See [`docs/TODO.md`](docs/TODO.md) for the per-milestone task lists and
> [`docs/Structure.md`](docs/Structure.md) for the per-file Real / Skeleton map.

### Prerequisites

- Python 3.11+
- Node.js 20+ (for the frontend)
- Docker + Docker Compose
- ≥ 16 GB RAM (for the self-hosted embedding model)

### Local Setup

```bash
git clone git@github.com:Odiethebest/Dcode.git
cd Dcode

# 1. Configure environment (EMBEDDING_MODEL, EMBEDDING_DIM, RERANKER_ENDPOINT,
#    JUDGE_MODEL — see .env.example for all keys and OD-2..OD-4 placeholders)
cp .env.example .env

# 2. Bring up the full stack
docker compose up -d

# 3. Apply database schema
make migrate

# 4. Run lint + typecheck + tests across services
make check
```

### Quick Smoke Test

These commands work against the M0 skeleton; responses are shape-correct stubs
until M1 / M2 wires the real pipeline.

```bash
# Submit a repo — returns 202 + stub repo_id
curl -X POST http://localhost:8000/api/v1/repos \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://github.com/psf/requests.git"}'

# Poll status — returns RepoStatusResponse shape (status="queued" until M1)
curl http://localhost:8000/api/v1/repos/<repo_id>/status

# Ask a question — SSE stream emits one stub `thought` then `final_answer`
curl -N -X POST http://localhost:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"repo_id":"00000000-0000-0000-0000-000000000000","query":"How is session handling implemented?"}'

# Bonus: agent tool manifest (debug)
curl http://localhost:8001/internal/tools | jq '.[].name'
```

---

## Deployment

Target: `dcode.odieyang.com` via Docker Compose. All services — API gateway, index worker, agent orchestrator, PostgreSQL + pgvector, Redis, RabbitMQ, and frontend — are orchestrated from a single `docker-compose.yml`. Per **NFR-7**, the system must come up from a clean checkout with a single `docker compose up`.

The self-hosted embedding service runs alongside in the same compose stack to avoid commercial API rate limits and cost during indexing (single repo = thousands of embedding calls). Commercial APIs (judge model, optionally reranker) are accessed via env-configured endpoints — never hardcoded — pending resolution of open decisions OD-2 through OD-4. See [`docs/DESIGN.md` §6](docs/DESIGN.md) for the full selection table and placeholder strategy.

---

## Evaluation Protocol

The evaluation harness is the core deliverable for verifying H1. It runs five baselines on the same question set and reports stratified metrics so that each layer's marginal contribution is isolated.

### Baseline Ladder

| Tier | System | Purpose |
|---|---|---|
| B0 | GitHub Search | Industry-standard keyword baseline |
| B1 | BM25 | Sparse retrieval reference |
| B2 | Vanilla Dense RAG | Single-path vector retrieval |
| B3 | Hybrid RAG | Dense + sparse + rerank |
| B4 | **Dcode** (hybrid + call graph + agent) | Full system |

### Question Taxonomy

| Label | Reasoning scope | H1 relevance |
|---|---|---|
| L1 | Single-file factual | Control bucket |
| L2 | Cross-file structural | **Primary H1 check** |
| L3 | Architecture-level | **Primary H1 check** |

H1 is expected to hold most strongly on L2 / L3, where flat similarity retrieval breaks down.

### Acceptance Thresholds

| Metric | Target |
|---|---|
| Retrieval (Recall@k / MRR / nDCG) | B4 strictly improves over every B0–B3; statistically significant on L2 / L3 |
| Pairwise Win-Rate vs Vanilla RAG (B2) | > 60% |
| Groundedness (programmatic) | ≥ 95% |

Question-set construction (manual / function-reverse-synthesis / GitHub issue mining), result schema, and the LLM-as-Judge protocol: [`docs/DESIGN.md` §2.4](docs/DESIGN.md) and [`docs/PLAN.md` §3](docs/PLAN.md).

---

## Key Design Decisions

**AST-level chunking, no fixed-window sliding**
A fixed-window slicer destroys function boundaries and drops import context, which makes retrieved chunks semantically meaningless once removed from their call site (`D-2.1.1`). Dcode chunks at function, method, class, and module-docstring boundaries via tree-sitter. The cost is a parser per language; the project bounds this by committing to Python only.

**Vectors and call graph in a single PostgreSQL instance**
A typical "RAG + graph" project would deploy Qdrant for vectors and a separate graph store for relationships. We co-locate both in PostgreSQL — pgvector for embeddings (HNSW + GIN), normal relational tables for symbols and edges. The win is operational: one connection pool, one backup boundary, one consistency story. The cost is some hand-rolling around hybrid retrieval, which we'd write either way.

**Hybrid retrieval is non-negotiable**
Code search needs both exact symbol match (`validate_token`) and semantic intent ("auth-related code"). Dense-only loses the first; sparse-only loses the second (`D-2.2.1`). Dcode runs both in parallel, fuses by Reciprocal Rank Fusion (k=60), then reranks with a cross-encoder. This also keeps the comparison against GitHub Search honest — GitHub Search is sparse-only, so beating it with hybrid is fair rather than a strawman.

**Groundedness as a hard guardrail, not just a metric**
For code-domain answers, inventing a symbol that doesn't exist is a project-killing failure mode. The groundedness check (`D-2.3.1`) is not optional — every citation in a final answer is regex-extracted, queried against the indexed symbol table, and stripped or flagged if missing. The same check produces the ≥ 95% acceptance number rather than reading from a model's self-report.

**Async indexing is for engineering credibility, not H1 validation**
The async pipeline (queue + worker + state machine + Redis-cached embeddings) does not contribute to H1 — a synchronous script could index the evaluation corpus and pass every metric. We build it anyway because (a) it makes the "platform" narrative coherent, and (b) it is where the engineering-interview signal lives. Priority order is strict: H1-critical work first, infrastructure second. See [`docs/PLAN.md` §4](docs/PLAN.md) for the full degradation path.

---

## Documentation

| Document | Role | Contents |
|---|---|---|
| **[`docs/DESIGN.md`](docs/DESIGN.md)**       | Technical authority   | System architecture, component design, data model, interface contracts, NFRs, technology selection, open decisions |
| **[`docs/PLAN.md`](docs/PLAN.md)**           | Execution authority   | Goals, scope, acceptance criteria, priority, team RACI, milestones (M1–M4), risk register, open-decision timeline |
| **[`docs/TODO.md`](docs/TODO.md)**           | Outstanding work      | Skeleton self-verification status, M1–M4 milestone task lists, M0 decisions log, open questions |
| **[`docs/Structure.md`](docs/Structure.md)** | File-tree walkthrough | Per-service file inventory tagged Real / Skeleton / M1–M4, cross-cutting concerns (multi-tenancy, cache, SSE, OD placeholders) |

---

## Team

| Name | Role |
|---|---|
| Ziqi (Odie) Yang | Tech Lead — indexing pipeline, agent orchestrator, system integration |
| Yuxin Liang | Retrieval & graph API, infrastructure, deployment |
| Yufan Li | Evaluation harness, frontend |

Independent project. Target execution window: 4 weeks.

---

## License

[Apache License 2.0](LICENSE).
