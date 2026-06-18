# Dcode Current Repository Structure

> 当前仓库结构说明。本文面向接手开发的组员，描述 **2026-06-17** 的实际代码状态，不再保留 M0 skeleton 标注。
>
> 权威关系：
> - [DESIGN.md](DESIGN.md)：目标架构、接口契约、数据模型
> - [PLAN.md](PLAN.md)：里程碑、团队分工、当前 demo 边界
> - [TODO.md](TODO.md)：剩余高优先级工作
> - [final_report.md](final_report.md) / [h1_decision.md](h1_decision.md)：当前评测快照与 H1 结论

---

## 1. 总览

```text
Dcode/
├── packages/shared/   shared schemas, settings, DB models, SSE events, cache keys
├── apps/api/          public FastAPI gateway, repo indexing API, query SSE proxy
├── apps/worker/       RabbitMQ consumer and repository indexing pipeline
├── apps/agent/        LangGraph agent service with tools and groundedness checks
├── apps/eval/         offline evaluation harness and baseline runners
├── apps/frontend/     React/Vite UI for indexing, querying, and comparison
├── infra/             Dockerfiles, Alembic migrations, Postgres init
├── scripts/           local helper scripts
├── results/           recorded evaluation outputs
└── docs/              project design, plan, status, and decision records
```

The public entry point is `apps/api`. The frontend talks only to `/api/v1/*`; it does not call the agent or database directly. The agent and retrieval/graph routes remain internal surfaces protected by an internal API key.

---

## 2. Workspace Root

| Path | Current role |
|---|---|
| `pyproject.toml` | uv workspace root for the Python packages; shared ruff, mypy, pytest config |
| `uv.lock` | locked Python dependency graph |
| `Makefile` | local commands for lint, typecheck, tests, migrations, smoke checks, compose lifecycle |
| `docker-compose.yml` | local development stack |
| `docker-compose.prod.yml` | production-shaped stack with frontend/nginx public exposure |
| `.env.example` | local env template with required secret placeholders |
| `.env.production.example` | production env template with required secret placeholders |
| `README.md` | project overview, API summary, setup, evaluation, docs map |
| `results/` | committed smoke and B2/B3/B4 evaluation snapshots |

Local `.env` is intentionally ignored and should not be committed.

---

## 3. Shared Package

`packages/shared` is the cross-service source of truth.

| Path | Current role |
|---|---|
| `src/dcode_shared/schemas.py` | Pydantic API schemas and enums used by API, agent, worker, eval, and frontend mirrors |
| `src/dcode_shared/events.py` | typed SSE event payloads and `sse_encode` wire helper |
| `src/dcode_shared/cache.py` | canonical Redis key builders for embeddings, tool cache, query cache, and job state |
| `src/dcode_shared/settings.py` | shared pydantic-settings configuration, including embedding/reranker/judge placeholders |
| `src/dcode_shared/internal.py` | internal API key dependency helper |
| `src/dcode_shared/db/models.py` | SQLAlchemy models for `repos`, `chunks`, `symbols`, `edges` |
| `src/dcode_shared/db/session.py` | async engine/session factory |
| `tests/` | schema roundtrip, metadata, cache key, and config hardening tests |

Current boundary: `EMBEDDING_MODEL=stub` remains the default. Real embedding and reranker integration should preserve these shared settings as the contract.

---

## 4. API Gateway

`apps/api` is the public FastAPI service.

| Path | Current role |
|---|---|
| `src/dcode_api/main.py` | FastAPI app, health endpoint, CORS, router registration |
| `src/dcode_api/deps.py` | DB, Redis, RabbitMQ publisher, and agent client dependencies |
| `src/dcode_api/routes/repos.py` | `POST /api/v1/repos`, repo URL validation, durable repo row, RabbitMQ publish after commit, status reads |
| `src/dcode_api/routes/query.py` | `POST /api/v1/query` SSE proxy to agent with query cache support |
| `src/dcode_api/routes/internal.py` | internal retrieval and graph lookup routes used by agent tools and eval baselines |
| `tests/` | public API, internal API, query SSE, route validation tests |

Important current behavior:

- Repo submission rejects localhost/private IP targets.
- Repo row is committed before RabbitMQ publish, avoiding the worker race where a job could be consumed before the DB row exists.
- If RabbitMQ publish fails after commit, the repo is marked failed instead of remaining queued forever.
- Query-side dense retrieval is wired as a future path, but in stub embedding mode the route degrades to sparse retrieval plus identity rerank.

---

## 5. Worker

`apps/worker` consumes index jobs and builds the repository index.

| Path | Current role |
|---|---|
| `src/dcode_worker/main.py` | RabbitMQ consume loop with shutdown handling |
| `src/dcode_worker/pipeline.py` | monotonic state machine: `queued -> cloning -> parsing -> embedding -> graphing -> ready` or `failed` |
| `src/dcode_worker/context.py` | `PipelineContext` passed between stages |
| `src/dcode_worker/models.py` | internal parsed/chunked data structures |
| `src/dcode_worker/stages/clone.py` | shallow git clone |
| `src/dcode_worker/stages/parse.py` | Python file discovery and stdlib `ast` parsing |
| `src/dcode_worker/stages/chunk.py` | AST-boundary chunks for module docs, functions, classes, and methods |
| `src/dcode_worker/stages/embed.py` | embedding cache and persistence path; currently defaults to `StubEmbeddingClient` |
| `src/dcode_worker/stages/graph.py` | symbol table and module import edges |
| `tests/` | clone/parse/chunk, embedding, graph, and pipeline tests |

Current boundaries:

- Parsing uses Python `ast`, not tree-sitter.
- Graph v1 persists modules, functions, classes, methods, and internal module import edges.
- Calls, richer references, and inheritance are still high-priority follow-up work.
- Real code embedding is not connected yet.

---

## 6. Agent

`apps/agent` is an internal FastAPI service that streams answer generation through LangGraph.

| Path | Current role |
|---|---|
| `src/dcode_agent/main.py` | `/healthz`, `/internal/tools`, `/internal/query`; builds runtime dependencies and streams graph output |
| `src/dcode_agent/graph.py` | rule-based multi-step LangGraph loop: plan, tool call, synthesize, groundedness check |
| `src/dcode_agent/state.py` | `AgentState` and step cap |
| `src/dcode_agent/sse.py` | typed SSE emitter backed by an async queue |
| `src/dcode_agent/groundedness.py` | citation extraction and verification against indexed DB rows |
| `src/dcode_agent/tools/` | 8 registered tools |
| `tests/` | graph planning, groundedness, SSE, tool registry, and tool execution tests |

Registered tools:

| Tool | Purpose |
|---|---|
| `search_code` | internal retrieval search |
| `read_file` | read repo file ranges from indexed/checked-out content |
| `find_definition` | symbol definition lookup |
| `find_references` | reverse graph/reference lookup |
| `get_dependencies` | module dependency lookup |
| `get_file_outline` | file-level symbol outline |
| `grep` | exact text search over repo files |
| `list_directory` | repository directory navigation |

Current boundaries:

- Planner is rule-based, not LLM-driven.
- Synthesis is template-based, not LLM-generated prose.
- Multi-step queries are supported for markers such as `how`, `flow`, `end-to-end`, `auth`, and `wired`, but the logic is deterministic.
- Groundedness verification is real and remains a non-disableable guardrail.

---

## 7. Evaluation

`apps/eval` runs offline baselines and writes reproducible metrics.

| Path | Current role |
|---|---|
| `src/dcode_eval/run.py` | CLI for single-baseline and suite runs; writes config, per-question rows, metrics, taxonomy breakdown, and H1 report |
| `src/dcode_eval/baselines/` | B0-B4 baseline interfaces and implementations |
| `src/dcode_eval/metrics/retrieval.py` | Recall@k, MRR, nDCG |
| `src/dcode_eval/metrics/groundedness.py` | groundedness metric types |
| `src/dcode_eval/metrics/judge.py` | Judge ABC and stub implementation |
| `src/dcode_eval/questions/` | question model and JSONL loader |
| `tests/` | baseline, metrics, dataset, and runner tests |

Current baseline status:

| Baseline | Status |
|---|---|
| B0 GitHub Search | interface exists; live GitHub Search integration not implemented |
| B1 BM25 | available as sparse retrieval reference path |
| B2 Vanilla RAG | implemented for current harness, but dense path collapses while embeddings are stubbed |
| B3 Hybrid RAG | implemented for current harness, but dense/rerank gains are not present in stub mode |
| B4 Full System | calls the agent/internal system path |

Current results are committed under `results/eval-suite/`. The recorded H1 conclusion is unsupported because B4 does not beat B2/B3 on L2/L3 under the current stub embedding and identity rerank constraints.

---

## 8. Frontend

`apps/frontend` is a React 18 + TypeScript + Vite SPA.

| Path | Current role |
|---|---|
| `src/App.tsx` | app shell and routes |
| `src/pages/IndexPage.tsx` | repo submission and status polling UI |
| `src/pages/QueryPage.tsx` | query UI and live SSE rendering |
| `src/pages/ComparePage.tsx` | recorded B2/B3/B4 comparison view |
| `src/api/client.ts` | API client and SSE parser |
| `src/api/types.ts` | frontend mirror of shared API types |
| `src/components/RepoStatusBadge.tsx` | status display component |
| `src/demo/evalSnapshot.ts` | static comparison data derived from recorded results |
| `tests/` | app, index, query, compare, and SSE parser tests |

Current boundaries:

- Frontend uses a checked-in snapshot for Compare rather than loading arbitrary result directories.
- Types are manually mirrored rather than generated from OpenAPI.
- UI is demo-oriented and intentionally smaller than a full product surface.

---

## 9. Infra

| Path | Current role |
|---|---|
| `infra/docker/api.Dockerfile` | API image |
| `infra/docker/worker.Dockerfile` | worker image |
| `infra/docker/agent.Dockerfile` | agent image with repo search tooling |
| `infra/docker/frontend.Dockerfile` | production frontend static build served by nginx |
| `infra/migrations/env.py` | Alembic metadata wiring |
| `infra/migrations/versions/001_initial_schema.py` | initial schema, pgvector extension, indexes |
| `infra/postgres/init.sql` | pgvector extension initialization |
| `.github/workflows/ci.yml` | Python and frontend CI checks |

Deployment status:

- Production compose packaging exists.
- Secrets are required through env placeholders; weak defaults were removed.
- `dcode.odieyang.com` is still unresolved in the current project snapshot, so public demo validation remains open.

---

## 10. Cross-Cutting Contracts

### Repo Isolation

`repo_id` scopes repo rows, chunks, symbols, edges, cache keys, and eval rows. New retrieval or graph work should keep `repo_id` in every query predicate.

### Redis Keys

Use helpers from `packages/shared/src/dcode_shared/cache.py` only. Do not hand-build Redis keys in feature code.

| Key type | Purpose | Intended TTL |
|---|---|---|
| `embed:{model_id}:{hash}` | content-addressed embedding cache | permanent |
| `tool:{name}:{repo_id}:{hash}` | agent tool result cache | 24h |
| `query:{repo_id}:{hash}` | complete query cache | 1h |
| `job:{repo_id}` | live indexing state | 7d after completion |

### SSE Events

The event contract is defined in `packages/shared/src/dcode_shared/events.py`.

Current event names:

- `thought`
- `tool_call`
- `tool_result`
- `citation`
- `partial_answer`
- `final_answer`
- `error`

### Environment-Driven Model Swaps

The project keeps model/provider decisions behind environment variables and abstractions.

| Area | Current setting | Current implementation boundary |
|---|---|---|
| Embeddings | `EMBEDDING_MODEL`, `EMBEDDING_DIM` | defaults to stub vectors |
| Reranker | `RERANKER_ENDPOINT` | identity rerank |
| Judge | `JUDGE_MODEL` | stub judge only |
| Internal auth | `INTERNAL_API_KEY` | required for internal routes |

---

## 11. Recommended Next Owners

| Area | Best owner | Reason |
|---|---|---|
| Real embedding and query-side dense retrieval | Yuxin | retrieval quality and infra boundary |
| Real reranker | Yuxin | same retrieval API contract |
| Calls/references/inheritance graph expansion | Yuxin with Odie review | shared worker/retrieval contract |
| Question set expansion and Judge/pairwise | Yufan | eval ownership |
| Compare UI result refresh | Yufan | frontend/eval boundary |
| Integration, agent boundary, final documentation | Odie | cross-service consistency |
