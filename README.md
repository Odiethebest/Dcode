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

**Reviewing this project?** Read this page, then
[`docs/en/Final_Report.md`](docs/en/Final_Report.md) for the verdict, then run it
and click a citation — that interaction is the product. Full document set under
[Documentation](#documentation).

---

## Overview

When a new engineer joins a mature codebase, the useful questions are relational: "how is auth implemented end to end?", "what depends on this module?", "who calls this function?". Mainstream tools usually optimize for literal search or text similarity, which misses the structure behind those questions.

| Tool category | Representative | Limitation |
|---|---|---|
| Keyword search | GitHub Search, ripgrep | Literal match only; lacks semantic intent |
| Flat vector RAG | Standard RAG implementations | Text similarity only; loses call relationships |
| General chat assistants | Generic LLM apps | Lacks grounded codebase context; citation hallucination |

Dcode builds a dual index — semantic vectors plus a static call graph — and exposes it through a ReAct agent. Every citation presented as code evidence in a final answer is verified against the index before reaching the user; ordinary inline code remains formatting rather than an implicit citation.

### What it handles

| Concern | Mechanism |
|---|---|
| Async indexing | Job queue + worker with monotonic state machine (`queued → cloning → parsing → embedding → graphing → ready`) |
| Chunk granularity | AST boundary chunks via Python `ast` |
| Call graph | AST-built symbol table, module import edges, and best-effort intra-repo call edges |
| Hybrid retrieval | Sparse + dense candidate retrieval, RRF fusion, optional cross-encoder reranking |
| Multi step reasoning | LangGraph state machine, 11 tools, rule based ReAct loop |
| Multi-turn follow-ups | Client-supplied bounded history, history-aware cache keys, and standalone-query contextualization |
| Answer presentation | Current-question language is preserved; Markdown math renders through KaTeX |
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
- **Retrieval Layer**: hybrid search + atomic graph queries (`find_definition`, `find_references`, bidirectional `get_call_neighbors`, dependencies, and file outlines)
- **Storage**: PostgreSQL + pgvector as the single store for vectors and graph data, plus Redis for embedding, tool result, and query caches
- **Evaluation Harness** (offline): five level baseline runner with stratified metrics

**Infrastructure**

- **Database**: PostgreSQL 15 with pgvector (HNSW on `embedding`); sparse retrieval
  is an application-side Okapi BM25 index cached per repository generation
- **ORM / Migrations**: SQLAlchemy 2.0 async + Alembic
- **Queue**: RabbitMQ with `aio-pika` client
- **Python workspace**: `uv` workspaces (7 members) + Hatch backend
- **Frontend**: React 18 + TypeScript (strict) + Vite + Tailwind + TanStack Query
- **Apps**: FastAPI gateway + worker + standalone agent service + embedding sidecar + reranker sidecar + frontend, orchestrated by Docker Compose

Full architecture, component design, and design decisions: [`docs/en/Technical_Design.md`](docs/en/Technical_Design.md).

---

## Data Model

Four runtime ORM tables are isolated by `repo_id` for multi-tenancy. Vectors and
the call graph live in the same PostgreSQL instance, eliminating a separate
vector service. The migration schema also contains an append-only `index_runs`
provenance table and `repos.current_index_run_id`; the current worker does not
populate either yet, so they are recorded as unfinished integration rather than
described as an active audit trail.

### Entity Hierarchy

```
repos (1) ──── (N) chunks
   │
   └── (1) ──── (N) symbols ──── (M) edges
                     │
                     └── (linked) chunks
```

### Schema Highlights

`chunks` is one AST-boundary slice per row. Dense retrieval uses `embedding
VECTOR(N)` under an HNSW index; sparse retrieval builds a code-tokenized Okapi
BM25 corpus from `symbol_name`, `file_path`, `signature`, and `content`. The
process-local BM25 corpus is keyed by `repos.index_revision`, which the worker
increments atomically whenever it replaces a repository's chunks. `N` comes from
`EMBEDDING_DIM` and is **fixed at migration time**.

`symbols` + `edges` form the call graph. `edges` carries `edge_type` (calls /
imports / inherits / references) and is indexed in **both** directions, on
`source_id` and on `target_id` — which is what makes the reverse lookup behind
*who calls this?* a single indexed query rather than a scan.

Authoritative schema: the Alembic migrations under `infra/migrations/`. Design
reasoning, storage topology, and the Redis keyspace:
[`docs/en/Technical_Design.md`](docs/en/Technical_Design.md).

---

## API Reference

### Indexing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/repos` | Submit a repo URL for indexing; returns `202 Accepted` with `repo_id` |
| `GET`  | `/api/v1/repos/{repo_id}/status` | Index progress and per-stage status |

```http
POST /api/v1/repos          { "url": "https://github.com/psf/requests.git" }
→ 202 Accepted              { "repo_id": "uuid", "status": "queued", "reused": false }
```

Submitting a URL that is already indexed returns `200` with `reused: true` and the
existing `repo_id` — no second clone.

### Query

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/query` | Ask a natural language question; returns an SSE stream |

```http
POST /api/v1/query          { "repo_id": "uuid", "query": "How is auth wired end to end?", "history": [] }
Accept: text/event-stream   → a stream of the events below
```

`history` is optional client-supplied conversation context. The gateway keeps the
most recent turns within configurable turn and character budgets, includes the
bounded history in the cache key, and sends it to the agent to resolve follow-up
questions. Services remain stateless between requests.

The supported Chinese/English answer contract follows the language of the
current question, independent of source-code or history language. LLM synthesis
is instructed to emit Markdown-compatible `$...$` / `$$...$$` math, and the
frontend also normalizes common `\(...\)` / `\[...\]` delimiters before rendering
with KaTeX.

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

### Inspector

Read-only, Postgres-only, scoped by `repo_id`. These back the click-a-citation
interaction.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/repos/{repo_id}/source` | Real indexed source behind a `file_path` + `line` or `symbol`, with the cited line marked. Degrades through chunk → symbol chunk → file outline → honest "not indexed at this granularity"; never 500s |
| `GET` | `/api/v1/repos/{repo_id}/neighbors` | Call-graph neighbours of a symbol — *called by* / *calls* / *references* — each with `file:line` so it is clickable |

Full request / response contracts and error semantics: [`docs/en/Technical_Design.md`](docs/en/Technical_Design.md).

---

## Getting Started

> **Status (2026-07-31)**: the full path — indexing, retrieval, agent SSE, the
> workbench frontend, the evaluation harness, production packaging — is implemented
> and running; `make check`, `make frontend-build`, and `make eval-smoke` pass.
> The current interaction path includes eleven tools, bilingual caller/callee
> routing, bounded multi-turn follow-ups, server-owned citation IDs,
> same-language answers, and KaTeX math rendering.
> H1 has been measured over 33 questions, five arms including a no-graph
> ablation, and **three repeated runs**. The recorded decision is
> **unsupported**: H1 is a conjunction of four comparisons and three of them
> clear — architecture-level questions beat both rivals by 3.4× and 4.9× the
> required margin, cross-file falls 0.006 short against hybrid+rerank. Across the
> three repeats that margin ranged wider than the bar itself, so see
> [Current Result](#current-result) before quoting any of it.
> The default stack runs stub models; the real ones are host sidecars needing
> three commands, not one (below). Status detail and what is unfinished:
> [`docs/en/Final_Report.md`](docs/en/Final_Report.md).

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

The default stack uses stub embedding and identity rerank to stay lightweight. The
real path — the one the recorded result was measured on — runs the models as
**host** sidecars, because `.env` points `EMBEDDING_ENDPOINT` / `RERANKER_ENDPOINT`
at `host.docker.internal:8002`/`8003`. That means **three** processes, not one:

```bash
make embedding-host   # :8002 — wait for "Embedding model ready"
make reranker-host    # :8003 — wait for "Reranker model ready"
make up               # core stack: postgres, redis, rabbitmq, api, agent, worker
```

Set `EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code`, `EMBEDDING_DIM=768`, and
`RERANKER_MODEL=BAAI/bge-reranker-v2-m3` in `.env`; recreate the database if it was
initialised at another dimension; start both sidecars **before** indexing. The
Docker `embedding` / `reranker` profiles are the alternative and need ~6 GB of
Docker RAM.

Two failure modes worth recognising: `make up` alone gives a stack whose API
reports healthy while every query dies at the embedding step, and a wall of Vite
`ECONNREFUSED` on `/api/v1/*` means the backend is down, not that the frontend
broke. Full runbook: [`docs/en/Operations.md`](docs/en/Operations.md).

### Quick Smoke Test

```bash
# Submit a repo → returns repo_id
curl -X POST http://localhost:8000/api/v1/repos \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://github.com/psf/requests.git"}'

# Poll until status=ready (a first real index takes several minutes and
# plateaus visibly at the embedding stage — that is real work, not a hang)
curl http://localhost:8000/api/v1/repos/<repo_id>/status

# Then ask
curl -N -X POST http://localhost:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"repo_id":"<repo_id>","query":"How does a Session prepare a request?"}'
```

---

## Deployment

Two compose entrypoints: `docker-compose.yml` for the developer stack, and
`docker-compose.prod.yml` where only the frontend is public and `/api/*` proxies to
the internal API service.

```bash
cp .env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml exec api \
  uv run alembic -c infra/migrations/alembic.ini upgrade head
```

The production stack is validated locally only — `dcode.odieyang.com` does **not**
resolve publicly, so the external-demo exit criterion is still open.

---

## Evaluation Protocol

The harness runs five baselines on the same question set and reports stratified metrics, so each layer's marginal contribution is isolated.

### Baseline Ladder

| Tier | System | Purpose |
|---|---|---|
| B0 | GitHub Search | Industry standard keyword baseline |
| B1 | BM25 | Sparse retrieval reference |
| B2 | Vanilla Dense RAG | Single path vector retrieval |
| B3 | Hybrid RAG | Dense + sparse + rerank, then the shared Agent synthesis path with structural expansion disabled |
| B4 | **Dcode** (hybrid + call graph + agent) | The same hybrid start and synthesis path, plus bounded structural expansion |

### Question Taxonomy

| Label | Reasoning scope | H1 relevance |
|---|---|---|
| L1 | Single file factual | Control bucket |
| L2 | Cross file structural | **Primary H1 check** |
| L3 | Architecture level | **Primary H1 check** |

H1 was expected to hold most strongly on L2 / L3, where flat similarity retrieval breaks down. The checked-in suite has **L1 5 / L2 16 / L3 12** — 33 questions after the 2026-07-31 expansion. Both levels are still small enough that one question moves the level composite by more than the margin the verdict turns on; a single question's weight only drops below the 0.05 decision margin at n > 20. Three pre-existing L2/L3 pairs also share ground truth (1.00 / 0.75 / 0.50), so the two levels are not independent samples. See the Final Report before reading either level in either direction.

### Acceptance Thresholds

The executable H1 decision in `dcode_eval.run` is deliberately narrower than the
additional product-quality gates tracked beside it:

| Check | Current rule |
|---|---|
| **Recorded H1 decision** | On both L2 and L3, B4 must beat B2 and B3 by at least `0.05` composite points. The composite is the mean of Recall@k, MRR and nDCG@k. Groundedness was a fourth term until 2026-07-31; dropping it multiplies every margin by 4/3, so the four-term reading is carried beside every verdict under `four_term`. |
| Pairwise Win-Rate vs Vanilla RAG (B2) | > 60% — **unmeasured**, the judge is still a stub and this value is not part of the current `h1_report` decision |
| Groundedness (programmatic) | ≥ 95% product guardrail — reported separately; the current B4 run clears it |

Question set construction, result schema, and the LLM-as-Judge protocol: [`docs/en/Technical_Design.md`](docs/en/Technical_Design.md).

### Current Result

**Protocol:** every agent arm — B2, B3, B3.5, B4 — shares one model, prompt,
citation verifier, groundedness path and step budget, and one scoring rule
(`uniform_final_verified_evidence_v2`, on ordered verified final evidence). They
differ only in retrieval mode and how far tool expansion is allowed to go. B1
answers from a template and is a retrieval reference outside the decision.

Measured over 33 questions, **averaged across three repeats**; each repeat's
independent verdict is recorded. Every figure below is generated from the results
directory by `scripts/sync_eval_artifacts.py`, never transcribed.

<!-- BEGIN generated: eval-suite-metrics -->

| Baseline | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` BM25 sparse | 0.390 | 0.563 | 0.376 | 1.000 |
| `B2` Dense RAG | 0.489 | 0.702 | 0.524 | 1.000 |
| `B3` Hybrid + rerank | 0.553 | 0.795 | 0.587 | 1.000 |
| `B4` Dcode (hybrid + call graph + agent) | 0.638 | 0.882 | 0.664 | 1.000 |

Source: `results/eval-h1-repeat3-2026-07-31/` · verdict written 2026-07-31 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · synthesis gpt-4o-mini

The date is **committed provenance, not harness output** — the harness writes no timestamp. Its observation basis and limits are recorded in `results/eval-h1-repeat3-2026-07-31/provenance.json`.

<!-- END generated: eval-suite-metrics -->

<!-- BEGIN generated: eval-h1-verdict -->

**Decision: `unsupported`**

H1 is supported only if B4 beats **both** B2 and B3 by at least `0.050` composite points on **both** L2 and L3.

| Level | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | Cleared |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` cross-file | 16 | 0.579 | 0.671 | 0.715 | +0.136 | +0.044 | no |
| `L3` architecture | 12 | 0.384 | 0.462 | 0.632 | +0.247 | +0.169 | yes |

<!-- END generated: eval-h1-verdict -->

Four things a reader should take from that table, stated plainly:

1. **H1 is unsupported because it is a conjunction, and three of its four
   comparisons clear.** Architecture questions beat both rivals — 3.4× the bar
   against hybrid+rerank, 4.9× against dense RAG — in all three repeats.
   Cross-file beats dense RAG by 2.7× and falls 0.006 short against
   hybrid+rerank. Four of four is required, so the verdict is `unsupported`.
2. **The margin is less stable than the bar it is measured against.** Across
   three identical repeats the cross-file margin was +0.038, +0.006 and +0.088 —
   a range of 0.083 — and **repeat 3 returned `supported` by itself**. Every
   single-run "near miss" in this repository's history sits inside that range.
   Resolving a 0.006 difference by repetition would take runs in the order of
   100; the remedy is more L2 questions, not more runs and not more tuning.
3. **The call graph works and is not what carries the result.** The `B3.5` arm —
   the full agent with graph tools disabled, everything else identical — puts the
   graph at +0.022 / +0.023 and the agent's multi-step evidence gathering at
   +0.147 on architecture questions. Without that ablation the +0.147 would have
   been reported as the graph's.
4. **The composite has three terms, and that is a lowered bar.** Groundedness was
   removed after four runs had missed the four-term version. It is 1.000 for
   every arm, so removing it multiplies margins by 4/3 — the same as a 0.0375
   threshold. Both readings live in `h1_report.json`; both return `unsupported`.

Full reasoning, including the pre-registered prediction this run falsified:
[`docs/en/Final_Report.md`](docs/en/Final_Report.md).

`results/eval-suite/` is an **earlier stub-model run**, kept for history and
explicitly not the current conclusion — see [`results/README.md`](results/README.md).

---

## Key Design Decisions

**AST boundary chunking**
Dcode chunks code at function, method, class, and module docstring boundaries via Python `ast` (`D-2.1.1`). This keeps import context and symbol boundaries attached to retrieved chunks, which makes the evidence easier to cite and verify.

**Vectors and call graph in a single PostgreSQL instance**
`pgvector` stores embeddings under an HNSW index; the retained `tsv` column has
a dormant GIN index, while ordinary relational tables store symbols and edges.
This gives one connection pool and one backup
boundary, but not one atomic index-generation transaction: chunks and graph rows
commit in separate worker stages, and the inspector reads source and neighbours
through separate requests. A failed graph stage can therefore leave new chunks
beside stale or missing graph rows until a successful re-index. The tradeoff is
custom hybrid-retrieval and consistency logic.

**Hybrid retrieval is required**
Code search needs exact symbol matching *and* semantic intent. Code-tokenized
Okapi BM25 and dense retrieval run in parallel, fuse by Reciprocal Rank Fusion
(`k=60`, dense:sparse weight `2:1` by default), then rerank through a cross
encoder (`D-2.2.1`). The checked-in
current real-model run records `okapi_bm25_v1`, its tokenizer, fields, `k1`,
`b`, and corpus revision, so the corrected sparse path is now part of the
measured baseline ladder. The earlier lexical snapshot remains under
`results/eval-real/` as historical evidence.

**Groundedness as a hard guardrail**
Inventing a symbol that does not exist is the critical failure mode for code answers. The check (`D-2.3.1`) extracts every citation from a final answer, verifies it against the indexed symbol table, and strips what it cannot verify. It is deliberately scored on the draft **before** redaction, which is why the guardrail can visibly fail. The current evidence-ID run clears it without changing that scoring rule; counting only surviving citations would make the number meaningless: [`docs/en/Honesty_Constraints.md`](docs/en/Honesty_Constraints.md).

**Async indexing supports the platform story**
H1 could be evaluated with a simpler indexing script; the queue, worker, state machine, and cached embeddings exist to make this usable as a service. Priority order stayed strict regardless: H1-critical work first, infrastructure second.

---

## Documentation

Five documents. `docs/en/` is authoritative.

| Document | Contents |
|---|---|
| **[`docs/en/Final_Report.md`](docs/en/Final_Report.md)** | **The acceptance core.** Implemented system, the evaluation numbers, the H1 decision and why, iteration history, re-open criteria, outstanding work, known limits, and what was and was not verified |
| **[`docs/en/Honesty_Constraints.md`](docs/en/Honesty_Constraints.md)** | What the interface is allowed to assert, and the reasoning behind each rule. Most are pinned by tests |
| **[`docs/en/Technical_Design.md`](docs/en/Technical_Design.md)** | Technical authority: repository layout, architecture, service boundaries, data model, API contracts, NFRs, technology choices |
| **[`docs/en/Operations.md`](docs/en/Operations.md)** | Running the stack, the real-model path, the evaluation harness, and the operational gotchas worth knowing before you hit them |
| **[`docs/en/Agentic_Workflow.md`](docs/en/Agentic_Workflow.md)** | How Claude Code, Codex, and Cursor were cross checked during development |

Colocated with what they describe: [`results/README.md`](results/README.md) (which
recorded run is the current conclusion), [`design/README.md`](design/README.md)
(the HTML prototypes the UI was built from), and
[`CLAUDE.md`](CLAUDE.md) (operational notes for agent sessions).

[`docs/archive/`](docs/archive) holds historical records — the development-era
problem register and its changelog, the executed frontend redesign brief, the
retired Chinese doc set, and superseded planning notes. Every file there carries a
banner saying so. Not current guidance.

**Reviewing this?** Read this page, then the Final Report for the verdict, then
run it and click a citation — that interaction is the product.

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
