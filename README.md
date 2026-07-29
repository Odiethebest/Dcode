# Dcode: Structure Aware Code Understanding Platform

> A retrieval platform for codebase onboarding. Dcode pairs semantic vector indexing with a static call graph, then queries both through a ReAct agent that returns programmatically verified citations.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-state%20machine-FF6F00)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%20+%20pgvector-4169E1?logo=postgresql)](https://github.com/pgvector/pgvector)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

**Development workflow:** [How the team cross checked Claude Code, Codex, and Cursor during implementation](docs/en/Agentic_Workflow.md)

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
- [Team](#team)

**Reviewing this project?** [`docs/README.md`](docs/README.md) has a three-step
path. The short version: this page, then
[`docs/en/Final_Report.md`](docs/en/Final_Report.md) for the verdict, then run it
and click a citation.

| Document | What it answers |
|---|---|
| [Final Report](docs/en/Final_Report.md) | Does the claim hold? Numbers, the H1 decision, and what would re-open it |
| [Honesty Constraints](docs/en/Honesty_Constraints.md) | What the UI is allowed to assert, and why — most rules are test-pinned |
| [Technical Design](docs/en/Technical_Design.md) | Architecture, contracts, data model |
| [Repository Structure](docs/en/Repository_Structure.md) | Where everything lives |
| [Final Report](docs/en/Final_Report.md#outstanding-work) | What is unfinished, including known regressions |
| [results/](results/README.md) | Which recorded run is the current conclusion |

---

## Overview

When a new engineer joins a mature codebase, the useful questions are relational: "how is auth implemented end to end?", "what depends on this module?", "who calls this function?". Mainstream tools usually optimize for literal search or text similarity, which misses the structure behind those questions.

| Tool category | Representative | Limitation |
|---|---|---|
| Keyword search | GitHub Search, ripgrep | Literal match only; lacks semantic intent |
| Flat vector RAG | Standard RAG implementations | Text similarity only; loses call relationships |
| General chat assistants | Generic LLM apps | Lacks grounded codebase context; citation hallucination |

Dcode is a structure aware retrieval platform. It asynchronously builds a dual index with semantic vectors and a static call graph, then exposes that index through a ReAct agent with multiple tools. Every code reference in a final answer is verified against the index before reaching the user.

### What it handles

| Concern | Mechanism |
|---|---|
| Async indexing | Job queue + worker with monotonic state machine (`queued → cloning → parsing → embedding → graphing → ready`) |
| Chunk granularity | AST boundary chunks via Python `ast` |
| Call graph | AST-built symbol table, module import edges, and best-effort intra-repo call edges |
| Hybrid retrieval | Sparse + dense candidate retrieval, RRF fusion, optional cross-encoder reranking |
| Multi step reasoning | LangGraph state machine, 8 tools, rule based ReAct loop |
| Hallucination control | Programmatic groundedness check with a required ≥ 95% threshold |
| Reproducible evaluation | Five level baseline ladder + L1/L2/L3 question taxonomy |
| Multi-tenancy | All chunks / symbols / jobs isolated by `repo_id` |

---

## Core Hypothesis (H1)

> **On cross file and architecture level code understanding tasks, the combination of structure aware indexing (semantic vectors + a code call graph) with tool based agent orchestration achieves significant and reproducible improvements over flat vector RAG and keyword search baselines, measured by standard IR metrics and end to end answer quality.**

The project's engineering investment serves this **falsifiable** hypothesis. If acceptance metrics in the [evaluation protocol](#evaluation-protocol) fail, H1 is recorded as unsupported. Thresholds stay fixed after evaluation begins.

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
                              │   AST    │  │ hybrid + graph   │
                              └────┬─────┘  └────┬─────────────┘
                                   │ write       │ read
                                   ▼             ▼
                              ┌──────────────────────────────┐
                              │ PostgreSQL + pgvector + Redis│
                              └──────────────────────────────┘
```

**Components**

- **API Gateway** (FastAPI): auth, tenant scoped routing, SSE termination
- **Index Worker**: `clone → Python AST chunk → embed → graph rebuild → persist`
- **Agent Orchestrator**: LangGraph state machine with rule-based planning, tools, optional LLM answer synthesis (`SYNTHESIS_MODEL`), and a groundedness guardrail
- **Retrieval Layer**: hybrid search + atomic graph queries (`find_definition`, `find_references`, `get_dependencies`, `get_file_outline`)
- **Storage**: PostgreSQL + pgvector as the single store for vectors and graph data, plus Redis for embedding, tool result, and query caches
- **Evaluation Harness** (offline): five level baseline runner with stratified metrics

**Infrastructure**

- **Database**: PostgreSQL 15 with the pgvector extension (HNSW on `embedding`, GIN on `tsv`)
- **ORM / Migrations**: SQLAlchemy 2.0 async + Alembic
- **Queue**: RabbitMQ with `aio-pika` client
- **Python workspace**: `uv` workspaces (7 members) + Hatch backend
- **Frontend**: React 18 + TypeScript (strict) + Vite + Tailwind + TanStack Query
- **Apps**: FastAPI gateway + worker + standalone agent service + embedding sidecar + reranker sidecar + frontend, orchestrated by Docker Compose
- **Deployment target**: `dcode.odieyang.com` (DNS unresolved as of 2026-07-11)

Full architecture, component design, and design decisions: [`docs/en/Technical_Design.md`](docs/en/Technical_Design.md).

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
-- Chunks: AST boundary slices, vector and tsvector colocated for hybrid retrieval
CREATE TABLE chunks (
    id            UUID PRIMARY KEY,
    repo_id       UUID REFERENCES repos(id),
    file_path     TEXT NOT NULL,
    chunk_type    chunk_type,        -- function / method / class / module_doc
    parent_symbol TEXT,              -- enclosing class for methods (NULL otherwise)
    symbol_name   TEXT NOT NULL,
    signature     TEXT,              -- full def/class header (ast.unparse)
    start_line    INT, end_line INT,
    imports       JSONB,
    content       TEXT,
    embedding     VECTOR(N),         -- N from EMBEDDING_DIM env var
    tsv           TSVECTOR           -- BM25 / full-text
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

Full schema, indexes, and Redis key naming conventions: [`docs/en/Technical_Design.md` §3](docs/en/Technical_Design.md).

---

## API Reference

### Indexing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/repos` | Submit a repo URL for indexing; returns `202 Accepted` with `repo_id` |
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
| `POST` | `/api/v1/query` | Ask a natural language question; returns an SSE stream |

```http
POST /api/v1/query
Content-Type: application/json
Accept: text/event-stream

{
  "repo_id": "uuid",
  "query": "How is authentication wired end to end?"
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

Full request / response contracts and error semantics: [`docs/en/Technical_Design.md` §4](docs/en/Technical_Design.md).

---

## Getting Started

> **Status (2026-07-29)**: indexing, retrieval, agent SSE, the workbench frontend,
> the evaluation harness, and production packaging are implemented and running.
> `make check`, `make frontend-build`, and `make eval-smoke` pass locally.
> H1 has been measured on a **full real-model run** (Jina v2-base-code 768-dim +
> BGE reranker v2-m3 + gpt-4o-mini) and the recorded decision is **unsupported** —
> see [Current Result](#current-result) for the numbers and for why the call
> graph's contribution is unmeasured rather than absent.
> The default stack still runs `EMBEDDING_MODEL=stub` / `RERANKER_MODEL=stub`;
> the real models are host sidecars and need three commands, not one (below).
> See [`docs/en/Final_Report.md`](docs/en/Final_Report.md)
> for status detail, including what is unfinished.

### Prerequisites

- Python 3.11+
- Node.js 20+ (for the frontend)
- Docker + Docker Compose
- ≥ 16 GB RAM (for the locally hosted embedding model)

### Local Setup

```bash
git clone git@github.com:Odiethebest/Dcode.git
cd Dcode

# 1. Configure environment (EMBEDDING_MODEL, EMBEDDING_DIM, RERANKER_ENDPOINT,
#    JUDGE_MODEL; see .env.example for all keys and OD-2..OD-4 placeholders)
cp .env.example .env

# 2. Bring up the default stub-model stack
docker compose up -d

# 3. Apply database schema
make migrate

# 4. Run lint + typecheck + tests across services
make check
```

### Real Model Mode

The default stack uses stub embedding and identity rerank so local development
stays lightweight. The real path — the one the recorded result was measured on —
runs the models as **host** sidecars, because `.env` points
`EMBEDDING_ENDPOINT` / `RERANKER_ENDPOINT` at `host.docker.internal:8002`/`8003`.
That means **three** processes, not one:

```bash
make embedding-host   # :8002 — wait for "Embedding model ready"
make reranker-host    # :8003 — wait for "Reranker model ready"
make up               # core stack: postgres, redis, rabbitmq, api, agent, worker
```

1. Set `EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code`, `EMBEDDING_DIM=768`, and `RERANKER_MODEL=BAAI/bge-reranker-v2-m3` in `.env`.
2. Recreate the database if it was initialized with another embedding dimension.
3. Start both sidecars **before** indexing — or use the `embedding` / `reranker`
   Docker Compose profiles instead, which need ~6 GB of Docker RAM.
4. Re-index the target repository before running evaluation.

Two failure modes worth recognising. `make up` alone gives a stack whose API
reports healthy while every query dies at the embedding step. And a wall of
Vite `ECONNREFUSED` on `/api/v1/*` in the dev-server log means the backend is
down, not that the frontend broke.

### Quick Smoke Test

These commands exercise the running stack.

```bash
# Submit a repo
curl -X POST http://localhost:8000/api/v1/repos \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://github.com/psf/requests.git"}'

# Poll status until `status=ready`
curl http://localhost:8000/api/v1/repos/<repo_id>/status

# Ask a question after indexing reaches `ready`
curl -N -X POST http://localhost:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"repo_id":"<repo_id>","query":"Where is `HTTPBasicAuth` defined?"}'
```

---

## Deployment

Two compose entrypoints are now tracked:

- `docker-compose.yml`: developer stack, with the frontend served as an nginx static SPA on `http://localhost:5173` and proxied `/api/*` calls.
- `docker-compose.prod.yml`: production oriented stack, where only the frontend is public and `/api/*` is proxied to the internal API service.

Production setup:

```bash
cp .env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml exec api \
  uv run alembic -c infra/migrations/alembic.ini upgrade head
```

As of **2026-07-11**, the production compose stack is validated locally, but
`dcode.odieyang.com` does **not** resolve publicly yet, so the external demo
exit criterion is still open. The production compose file currently keeps the
public frontend/API shape separate from the optional embedding and reranker
sidecars used in local development.

---

## Evaluation Protocol

The evaluation harness is the core deliverable for verifying H1. It runs five baselines on the same question set and reports stratified metrics so that each layer's marginal contribution is isolated.

### Baseline Ladder

| Tier | System | Purpose |
|---|---|---|
| B0 | GitHub Search | Industry standard keyword baseline |
| B1 | BM25 | Sparse retrieval reference |
| B2 | Vanilla Dense RAG | Single path vector retrieval |
| B3 | Hybrid RAG | Dense + sparse + rerank |
| B4 | **Dcode** (hybrid + call graph + agent) | Full system |

### Question Taxonomy

| Label | Reasoning scope | H1 relevance |
|---|---|---|
| L1 | Single file factual | Control bucket |
| L2 | Cross file structural | **Primary H1 check** |
| L3 | Architecture level | **Primary H1 check** |

H1 is expected to hold most strongly on L2 / L3, where flat similarity retrieval breaks down.

### Acceptance Thresholds

| Metric | Target |
|---|---|
| Retrieval (Recall@k / MRR / nDCG) | B4 strictly improves over every B0 through B3; statistically significant on L2 / L3 |
| Pairwise Win-Rate vs Vanilla RAG (B2) | > 60% |
| Groundedness (programmatic) | ≥ 95% |

Question set construction (manual / function reverse synthesis / GitHub issue mining), result schema, and the LLM as Judge protocol: [`docs/en/Technical_Design.md` §2.4](docs/en/Technical_Design.md) and [`docs/en/Project_Plan.md` §3](docs/en/Project_Plan.md).

### Current Result

Measured on the full real-model run. Every figure below is generated from the
results directory by `scripts/sync_eval_artifacts.py`, never transcribed.

<!-- BEGIN generated: eval-suite-metrics -->

| Baseline | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` BM25 sparse | 0.214 | 0.221 | 0.204 | 1.000 |
| `B2` Dense RAG | 0.474 | 0.325 | 0.333 | 1.000 |
| `B3` Hybrid + rerank | 0.542 | 0.596 | 0.508 | 1.000 |
| `B4` Dcode (hybrid + call graph + agent) | 0.542 | 0.596 | 0.508 | **0.916** ⚠️ below the 0.95 guardrail |

Source: `results/eval-real/` · recorded 2026-07-28 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · synthesis gpt-4o-mini

<!-- END generated: eval-suite-metrics -->

<!-- BEGIN generated: eval-h1-verdict -->

**Decision: `unsupported`**

H1 is supported only if B4 beats **both** B2 and B3 by at least `0.050` composite points on **both** L2 and L3.

| Level | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | Cleared |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` cross-file | 8 | 0.448 | 0.586 | 0.562 | +0.113 | −0.024 | no |
| `L3` architecture | 3 | 0.315 | 0.371 | 0.324 | +0.009 | −0.047 | no |

<!-- END generated: eval-h1-verdict -->

Three things a reader should take from that table, stated plainly:

1. **H1 is unsupported.** B4 clears the bar against dense RAG on cross-file
   questions and against nothing else. The threshold was fixed before the run
   and has not moved.
2. **Hybrid retrieval is validated.** `B1 < B2 < B3` is a clean ladder — this
   result is independent of the H1 verdict and it is the finding that held up.
3. **B4's groundedness falls below the 0.95 guardrail.** The agent sometimes
   emits a citation that fails verification. Unverifiable references are
   stripped from the delivered answer, but the score deliberately counts the
   draft *before* redaction, so a heavily-redacted answer still scores low.
   That is a real dip in a pre-registered guardrail and it is reported as one.

**Why B4 cannot currently beat B3:** B4's *scored* retrieval is the same hybrid
search as B3's, so the two rows match to the digit. The call-graph tools fire
later, inside the agent's answer, which this harness does not score. The graph's
contribution is therefore **unmeasured** — a diagnosed limitation of the
evaluation design, not evidence that the graph does not work. Full reasoning,
including the corrected scoring that would re-open H1:
[`docs/en/Final_Report.md`](docs/en/Final_Report.md).

`results/eval-suite/` is an **earlier stub-model run**, kept for history and
explicitly not the current conclusion — see [`results/README.md`](results/README.md).

---

## Key Design Decisions

**AST boundary chunking**
Dcode chunks code at function, method, class, and module docstring boundaries via Python `ast` (`D-2.1.1`). This keeps import context and symbol boundaries attached to retrieved chunks, which makes the evidence easier to cite and verify.

**Vectors and call graph in a single PostgreSQL instance**
Vectors and graph relationships live in PostgreSQL. `pgvector` stores embeddings with HNSW and GIN indexes, while normal relational tables store symbols and edges. This gives the system one connection pool, one backup boundary, and one consistency model. The tradeoff is additional custom logic around hybrid retrieval.

**Hybrid retrieval is required**
Code search needs exact symbol matching (`validate_token`) and semantic intent ("auth related code"). Dcode runs sparse and dense retrieval in parallel, fuses the candidates by Reciprocal Rank Fusion (`k=60`), then reranks them with a cross encoder (`D-2.2.1`). This keeps the comparison against GitHub Search fair because GitHub Search remains a sparse retrieval baseline.

**Groundedness as a hard guardrail**
For code answers, inventing a symbol that does not exist is a critical failure. The groundedness check (`D-2.3.1`) extracts every citation in a final answer, checks it against the indexed symbol table, and strips or flags missing references. The same check produces the ≥ 95% acceptance number from indexed evidence.

**Async indexing supports the platform story**
The async pipeline combines a queue, worker, state machine, and Redis cached embeddings. H1 can be evaluated with a simpler indexing script, but the asynchronous path makes the platform usable as a service and strengthens the engineering story. The priority order remains strict: H1 critical work first, infrastructure second. See [`docs/en/Project_Plan.md` §4](docs/en/Project_Plan.md) for the full degradation path.

---

## Documentation

| Document | Role | Contents |
|---|---|---|
| **[`docs/README.md`](docs/README.md)** | Documentation map | Reading order, en/ch document pairs, and archive boundaries |
| **[`docs/en/Technical_Design.md`](docs/en/Technical_Design.md)**       | Technical authority   | System architecture, component design, data model, interface contracts, NFRs, technology selection, open decisions |
| **[`docs/en/Project_Plan.md`](docs/en/Project_Plan.md)**           | Execution authority   | Goals, scope, acceptance criteria, priority, team RACI, milestones (M1 to M4), risk register, open decision timeline |
| **[`docs/en/Final_Report.md`](docs/en/Final_Report.md)**                   | Outstanding work      | Now carries its own outstanding-work section: remaining gaps, known limits, deployment follow-ups |
| **[`docs/en/Final_Report.md`](docs/en/Final_Report.md)** | Final report + H1 decision | Implemented system summary, evaluation snapshot, next steps, and the H1 judgment + re-open criteria |
| **[`docs/en/Repository_Structure.md`](docs/en/Repository_Structure.md)** | Current repository structure | Current service inventory, implementation boundaries, cross service contracts, suggested ownership |
| **[`docs/en/Sidecar_Smoke.md`](docs/en/Sidecar_Smoke.md)** | Integration smoke | Reproducible Jina v2, BGE reranker, 768-dim re-index, and agent smoke guide |
| **[`docs/en/Agentic_Workflow.md`](docs/en/Agentic_Workflow.md)** | Development workflow | How Claude Code, Codex, and Cursor were cross checked during development |
| **[`docs/archive/`](docs/archive)** | Historical notes | Original kickoff and execution roadmap retained for traceability only |

---

## Team

| Name | Role |
|---|---|
| Ziqi (Odie) Yang | Tech Lead: indexing pipeline, agent orchestrator, system integration |
| Yuxin(Lacey)Liang | Retrieval & graph API, infrastructure, deployment |
| Yufan Li | Evaluation harness, frontend |

Independent project. Target execution window: 4 weeks.

---

## License

[Apache License 2.0](LICENSE).
