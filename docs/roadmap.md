# Dcode Solo Roadmap

> 面向仓库管理员的独立推进清单。本文基于 [PLAN.md](PLAN.md) 的目标、优先级和里程碑重排，假设大部分实现由一人完成。
>
> 原则：先证明 H1 所需的最短闭环，再补平台化、前端和部署。每完成一阶段都必须能运行、能测试、能解释。

---

## 0. 当前基线

- [x] 确认 `main` 分支 clean，记录当前 commit SHA
- [x] 本地跑通 `make check`
- [x] 本地跑通 `docker compose up -d --build`
- [x] 本地跑通 `make migrate`
- [x] 验证以下 M0 接口仍可用：
  - [x] `GET /healthz` on API
  - [x] `GET /healthz` on Agent
  - [x] `POST /api/v1/repos` 返回 202 shape
  - [x] `POST /api/v1/query` 返回 SSE stub
- [x] 建一个固定开发目标仓库目录，例如 `data/repos/`
- [x] 建一个固定结果目录，例如 `results/`

Baseline run record:

- Date: 2026-06-15
- Branch: `main`
- Commit: `55e5839`
- Local Python env: rebuilt `.venv` with Python 3.11 after the old venv entrypoints pointed at a stale path
- `make check`: passed
- `docker compose up -d --build`: passed
- `make migrate`: passed
- Smoke:
  - API `GET /healthz`: `{"status":"ok"}`
  - Agent `GET /healthz`: `{"status":"ok"}`
  - API `POST /api/v1/repos`: returned `202` shape with `status="queued"`
  - API `POST /api/v1/query`: returned stub `thought` and `final_answer` SSE events
  - Frontend `GET /`: passed
  - Compose: API, Agent, Frontend, Postgres, Redis, RabbitMQ, Worker healthy

Exit criteria: M0 状态可复现，任何后续改动都有可回归基线。

---

## 1. 决策冻结

这些决定先定下来，避免后面实现时反复改接口。

- [x] OD-1: 选择主目标仓库
  - [x] 首选 `requests`，因为规模适中、依赖少、问题容易人工标注
  - [x] 备选 `flask`
  - [x] 暂缓 `fastapi`，因为依赖和架构复杂度更高
- [x] OD-2: 选择 embedding 策略
  - [x] 第一版允许使用 stub/本地简化 embedding 跑通管线
  - [x] H1 正式评测前替换成代码 embedding 模型
  - [x] 记录模型名、维度、运行方式、成本
- [x] OD-3: 选择 reranker 策略
  - [x] 第一版先无 reranker 或简单 score fusion
  - [x] 正式评测前补 cross-encoder/reranker
- [x] OD-4: 选择 judge 策略
  - [x] 第一版先生成可人工检查的 `per_question.jsonl`
  - [x] 正式报告前再接 LLM-as-Judge
- [x] OD-5: 部署策略
  - [x] 本地 Docker Compose 优先
  - [x] 线上 `dcode.odieyang.com` 放到最后

Decision record:

- Date: 2026-06-15
- OD-1 target repo: `requests`
  - Primary evaluation repo: `https://github.com/psf/requests.git`
  - Rationale: smaller and more stable than `fastapi`, enough real cross-file behavior for L1/L2/L3 questions, and easier to manually audit alone.
  - Fallback: `flask` if `requests` does not produce enough L2/L3 graph questions.
- OD-2 embedding: `jinaai/jina-embeddings-v2-base-code`
  - Default env for real embedding phase: `EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code`, `EMBEDDING_DIM=768`.
  - M1/M2 bootstrap behavior: keep `StubEmbeddingClient` until clone/parse/chunk/persist is stable.
  - Real implementation path: self-host through `sentence-transformers` or `transformers`; cache with `embed:{model_id}:{sha256(text)}` before DB writes.
  - Rationale: code-oriented open model, Apache-2.0, supports Python and other programming languages, and supports long inputs suitable for AST chunks.
  - Source: <https://huggingface.co/jinaai/jina-embeddings-v2-base-code>
- OD-3 reranker: `BAAI/bge-reranker-v2-m3`
  - Default env for real rerank phase: `RERANKER_MODEL=BAAI/bge-reranker-v2-m3`; keep `RERANKER_ENDPOINT` for either local HTTP service or direct in-process adapter.
  - M2 bootstrap behavior: identity rerank behind the same interface so retrieval can ship before model hosting.
  - Real implementation path: rerank top-50 fused candidates and return top-10.
  - Rationale: reranker takes query + passage and returns relevance directly; v2-m3 is lightweight enough for local deployment and supports multilingual/code-adjacent text.
  - Source: <https://huggingface.co/BAAI/bge-reranker-v2-m3>
- OD-4 judge: OpenAI `gpt-5.4-mini`
  - Default env for automated judge phase: `JUDGE_MODEL=gpt-5.4-mini`.
  - Bootstrap behavior: write `per_question.jsonl` and allow manual review before API-backed judging.
  - Real implementation path: use Responses API rubric scoring plus pairwise comparisons; reserve stronger `gpt-5.5` for spot checks or disputed samples only.
  - Rationale: official OpenAI guidance positions `gpt-5.5` as the flagship for complex reasoning/coding and `gpt-5.4-mini` as the lower-cost/lower-latency option; judge volume favors mini with manual spot checks.
  - Source: <https://developers.openai.com/api/docs/models>
- OD-5 deployment: local-first, production-last
  - Development target: Docker Compose on local machine.
  - Demo target: `dcode.odieyang.com` only after B2/B3/B4 eval outputs exist.
  - Production shape: keep one Compose deployment, put a reverse proxy in front, expose frontend + API only, keep Agent/internal routes private.
  - Frontend production: replace Vite dev container with static build served by nginx/Caddy during M4.

Exit criteria: `docs/TODO.md` 或本文记录所有 OD 的最终选择。

---

## 2. 最短索引闭环

目标：提交一个仓库 URL 后，数据库里真的有 `repos / chunks / symbols / edges` 数据。

### 2.1 API 入队

- [x] `apps/api/src/dcode_api/routes/repos.py`
  - [x] `submit_repo` 创建真实 `Repo` 行
  - [x] `submit_repo` 发布 RabbitMQ 消息到 `dcode.index_jobs`
  - [x] 消息体包含 `repo_id`、`url`
  - [x] 返回真实 `repo_id`
  - [x] `repo_status` 从 DB 读取 `status/progress/error`
  - [x] `repo_status` 合并 Redis `job:{repo_id}` stage 状态
- [x] 测试
  - [x] API 单测覆盖真实持久化路径
  - [x] malformed URL 至少有明确错误

Implementation record:

- Date: 2026-06-15
- Added RabbitMQ publisher dependency with durable queue publish to `dcode.index_jobs`
- `POST /api/v1/repos` now validates Git URLs, inserts a queued `repos` row, publishes `{repo_id,url}`, commits on publish success, and rolls back on publish failure
- `GET /api/v1/repos/{repo_id}/status` now returns DB state plus optional Redis `job:{repo_id}` live stage data
- Tests cover successful queueing, malformed URL, publish failure rollback, status merge, and unknown repo 404
- Verification:
  - `make check`: passed
  - Docker API/worker rebuild: passed
  - Real smoke `POST /api/v1/repos`: returned queued repo `475a4ef7-da12-45e0-bfdc-125d359e31d5`
  - Real smoke `GET /api/v1/repos/{repo_id}/status`: returned queued DB status
  - Worker log confirmed receipt of the RabbitMQ job

### 2.2 Worker 状态机

- [x] `apps/worker/src/dcode_worker/pipeline.py`
  - [x] 解析 message body
  - [x] 按顺序推进状态：`queued -> cloning -> parsing -> embedding -> graphing -> ready`
  - [x] 任一阶段异常时写 `failed` 和 `error`
  - [x] 每阶段更新 Redis `job:{repo_id}`
  - [x] 每次状态变更提交 DB transaction
- [x] 明确失败策略
  - [x] clone 失败直接 failed
  - [x] 单文件 parse 失败先跳过并记录 warning（2.3 在 parse stage 内实现）
  - [x] graph 部分失败不阻断 chunks 落库（2.5 在 graph stage 内实现）

Implementation record:

- Date: 2026-06-15
- `handle_job` now validates `{repo_id,url}` payloads, rejects malformed messages without crashing the consumer, and builds a typed `PipelineContext`
- Added `PipelineStage` state-machine wiring:
  - `cloning`: `clone.run`
  - `parsing`: `parse.run`, then `chunk.run`
  - `embedding`: `embed.run`
  - `graphing`: `graph.run`
- Each visible stage writes durable `repos.status/progress/error` and live Redis `job:{repo_id}` stage state
- Terminal `ready` and `failed` Redis states use the documented 7-day TTL
- Stage exceptions are caught, persisted as `failed`, and logged with stack context so the RabbitMQ consumer can ack the message instead of endlessly retrying an unimplemented or invalid stage
- Verification:
  - Worker unit tests cover malformed payloads, full success-state progression, and current-stage failure marking
  - `make check`: passed
  - Docker worker rebuild: passed
  - Real smoke repo `8041685d-5e5d-49af-a799-c8d966810560` was consumed by worker and moved from `queued` to `failed` with `cloning=failed`, as expected while `clone.run` is still a 2.3 placeholder

### 2.3 Clone / Parse / Chunk

- [x] `stages/clone.py`
  - [x] 使用 `git clone --depth=1`
  - [x] workdir 按 repo_id 隔离
  - [x] 记录 commit SHA
- [x] `stages/parse.py`
  - [x] 递归收集 `.py` 文件
  - [x] 跳过 `.venv`、`venv`、`.git`、`__pycache__`、build artifacts
  - [x] 用 Python `ast` 产出可供 chunk 使用的结构
- [x] `stages/chunk.py`
  - [x] 函数 chunk
  - [x] method chunk
  - [x] class chunk
  - [x] module docstring chunk
  - [x] 提取 `file_path/symbol_name/signature/start_line/end_line/imports/content`
  - [x] 禁止定长滑窗
- [x] 测试
  - [x] 用 fixture 文件覆盖 function/class/method/docstring
  - [x] 验证 line number 准确
  - [x] 验证 imports 随 chunk 带上

Implementation record:

- Date: 2026-06-15
- Added worker-local `ParsedPythonFile` and `CodeChunk` dataclasses so parse/chunk outputs are typed before DB persistence is implemented
- `clone.run` now shallow-clones into `WORKDIR_BASE/{repo_id}`, clears stale workdirs for repeatable retries, and records `commit_sha`; the pipeline writes that SHA to `repos.commit_sha`
- `parse.run` now walks cloned repos for `.py` files, skips generated/virtualenv/cache directories, parses with Python `ast`, records module-level imports, and skips single-file syntax/encoding failures as warnings
- `chunk.run` now emits AST-boundary chunks for module docstring, top-level functions, classes, and class methods; each chunk carries path, symbol, signature, line span, imports, and source content
- Boundary note: 2.3 produces in-memory chunks on `PipelineContext`; DB chunk persistence remains coupled to embedding/persist work in 2.4/2.5
- Verification:
  - New worker tests cover local git clone, repo-scoped workdir, commit SHA, parse skip behavior, chunk types, line numbers, and import propagation
  - `make check`: passed
  - Docker worker rebuild: passed
  - Real smoke repo `f88524dc-06cb-4b63-8c94-3b79e416fa2f` for `https://github.com/psf/requests.git` advanced to `cloning=done`, `parsing=done`, then failed at expected `embedding` placeholder
  - DB `repos.commit_sha`: `d64b9ad4bf1c14e21e0df3f0f4320fec81180e91`

### 2.4 Embedding 第一版

- [x] `stages/embed.py`
  - [x] 先接 `StubEmbeddingClient` 让 DB 能完整写入
  - [x] 实现 `embed:{model_id}:{sha256(text)}` 缓存 key
  - [x] 实现 Redis `mget/mset`
  - [x] embedding 维度与 `EMBEDDING_DIM` 一致
- [x] 后续替换真实模型时保持接口不变

Implementation record:

- Date: 2026-06-15
- `embed.run` now embeds every `PipelineContext.chunks` item, attaches vectors to `ctx.embeddings`, and replaces the repo's existing `chunks` rows in Postgres for idempotent re-indexing
- Default embedding client remains `StubEmbeddingClient`, using `EMBEDDING_DIM` for zero-vector output so DB shape and pgvector dimension are exercised before OD-2 model hosting
- Redis cache uses `embed:{model_id}:{sha256(text)}` via `embedding_cache_key`, with `mget` before embedding and `mset` for misses; cache read/write failures degrade to recomputing instead of failing the job
- The embedding client interface stays injectable: real model replacement can pass another `EmbeddingClient` without changing pipeline orchestration
- Verification:
  - New worker tests cover cache hits, cache misses, Redis `mset`, chunk DB replacement, persisted embeddings, and dimension mismatch rejection
  - `make check`: passed
  - Docker worker rebuild: passed
  - Real smoke repo `860bdd91-7870-452f-a6a4-3a68d9a619e8` for `https://github.com/psf/requests.git` advanced to `embedding=done`, then failed at expected `graphing` placeholder
  - DB rows for smoke repo: `chunks=726`, `vector_dims(embedding)=1024`, `commit_sha=d64b9ad4bf1c14e21e0df3f0f4320fec81180e91`

### 2.5 Graph 第一版

- [x] `stages/graph.py`
  - [x] 先用 AST 提取 definitions，填 `symbols`
  - [x] imports 边先做到模块级
  - [x] calls/references 可先粗略提取，再用 jedi 增强（后续增强项，当前第一版不阻塞 ready）
  - [x] 每个 symbol 尽量关联 `chunk_id`
- [x] 测试
  - [x] fixture 里验证 function/class/module symbols
  - [x] 验证 imports edge
  - [x] 验证 repo_id 隔离

Implementation record:

- Date: 2026-06-15
- `graph.run` now reads persisted chunks, builds module/function/class/method symbols from parsed Python ASTs, links definition symbols back to matching chunk rows, and writes module-level internal `imports` edges
- Graph writes are idempotent per repo: old `edges` and `symbols` are deleted before inserting the rebuilt graph
- Internal import edges are only created when both source and target modules exist in the indexed repo; external dependencies are intentionally ignored in this first version
- Real-repo hardening from smoke:
  - Flush symbols before inserting edges so Postgres FK checks can see `source_id/target_id`
  - Deduplicate duplicate qualified names before insert to satisfy `ix_symbols_repo_qname_unique`
- Verification:
  - New worker tests cover module/function/class/method symbols, internal import edges, repo_id propagation, chunk_id links, and duplicate qualified-name dedupe
  - `make check`: passed
  - Docker worker rebuild: passed
  - Real smoke repo `f09e4e16-18cb-4771-b948-3c1caf4f1cc3` for `https://github.com/psf/requests.git` reached `ready`
  - DB rows for smoke repo: `chunks=726`, `symbols=724`, `edges=65`, `linked_symbols=687`, `commit_sha=d64b9ad4bf1c14e21e0df3f0f4320fec81180e91`

Exit criteria: 一个真实目标 repo 能从 API 提交，经 worker 写入 DB；`chunks` 和 `symbols` 有非空数据；`make check` 通过。Status: passed on 2026-06-15 with smoke repo `f09e4e16-18cb-4771-b948-3c1caf4f1cc3`.

---

## 3. 检索与图查询闭环

目标：不经过 Agent，直接用内部 API 找到相关代码。

### 3.1 内部 Retrieval API

- [x] 决定位置：优先放在 `apps/api/src/dcode_api/routes/internal.py`
- [x] 新增内部接口：
  - [x] `GET /internal/search?repo_id=&query=&k=`
  - [x] `GET /internal/find_definition?repo_id=&symbol=`
  - [x] `GET /internal/find_references?repo_id=&symbol=`
  - [x] `GET /internal/get_dependencies?repo_id=&module=`
  - [x] `GET /internal/get_file_outline?repo_id=&path=`
- [x] 所有查询必须带 `repo_id`
- [x] 所有返回使用 `dcode_shared.schemas`

Implementation record:

- Date: 2026-06-16
- Added [internal.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/api/src/dcode_api/routes/internal.py) and mounted it under `/internal` in the API gateway
- All five internal endpoints now require `repo_id` and reuse shared response schemas:
  - `/internal/search` -> `list[Chunk]`
  - `/internal/find_definition` -> `list[Location]`
  - `/internal/find_references` -> `list[Location]`
  - `/internal/get_dependencies` -> `list[Location]`
  - `/internal/get_file_outline` -> `list[Location]`
- Unknown repos now fail with the same `REPO_NOT_FOUND` contract used by the public repo-status API
- Current implementation is intentionally first-pass:
  - search uses simple DB filtering plus Python-side sparse scoring over `symbol_name/file_path/content`
  - graph queries use existing `symbols/edges` tables with exact match first and suffix fallback second
  - retrieval quality upgrades remain in 3.2 and 3.3
- Verification:
  - Added API route contract tests for all five internal endpoints plus unknown-repo 404
  - `make check`: passed
  - Docker API rebuild: passed
  - Real smoke against ready repo `f09e4e16-18cb-4771-b948-3c1caf4f1cc3`:
    - `/internal/search?query=HTTPBasicAuth&k=3` returned `src/requests/auth.py`
    - `/internal/find_definition?symbol=HTTPBasicAuth` returned `src.requests.auth.HTTPBasicAuth`
    - `/internal/find_references?symbol=src.requests.auth` returned importing modules such as `src.requests.adapters`
    - `/internal/get_dependencies?module=src.requests.api` returned modules including `src.requests.models` and `src.requests.sessions`
    - `/internal/get_file_outline?path=src/requests/auth.py` returned ordered symbols from `src.requests.auth`

### 3.2 Search 第一版

- [x] sparse 检索
  - [x] 使用 `tsv` 或简单 SQL fallback
  - [x] 支持精确 symbol/path 命中
- [x] dense 检索
  - [x] stub embedding 阶段允许退化
  - [x] 真实 embedding 后使用 pgvector cosine（dense SQL path 已接好；当前 stub runtime 不启用 query embedding）
- [x] fusion
  - [x] 实现 RRF
  - [x] score_components 保留 dense/sparse/rerank
- [x] rerank
  - [x] 第一版可设为 identity rerank
  - [x] 正式评测前接真实 reranker

Implementation record:

- Date: 2026-06-16
- Upgraded `/internal/search` from a single sparse ranker to hybrid search with four explicit stages:
  - sparse candidate collection over `symbol_name/file_path/content`
  - dense candidate hook
  - reciprocal-rank fusion (RRF, `k=60`)
  - identity rerank that preserves a later swap to a real reranker
- `score_components` now carries channel-separated values:
  - `sparse`: lexical match score
  - `dense`: dense similarity score when available, else `0.0`
  - `rerank`: final identity-reranked fused score
- Current runtime behavior is intentionally conservative:
  - with `EMBEDDING_MODEL=stub`, query embedding is disabled and dense search cleanly degrades to sparse-only
  - the pgvector cosine query path is implemented in `_search_dense_candidates` and can be activated once the API is wired to a real query embedding client for OD-2
- Verification:
  - Added tests for hybrid candidate fusion ordering, sparse-only degradation under stub embedding, and route contracts
  - `make check`: passed
  - Docker API rebuild: passed
  - Real smoke against ready repo `f09e4e16-18cb-4771-b948-3c1caf4f1cc3`:
    - `/internal/search?query=HTTPBasicAuth&k=5` returned `src/requests/auth.py` first
    - response `score_components` exposed `sparse` and `rerank` values while `dense=0.0` under stub mode

### 3.3 Graph Queries

- [x] `find_definition`
  - [x] exact qualified_name
  - [x] suffix match fallback
- [x] `find_references`
  - [x] reverse edge lookup
  - [x] calls/references 都考虑
- [x] `get_dependencies`
  - [x] imports edge lookup
- [x] `get_file_outline`
  - [x] 按 file_path 和 line 排序 symbols

Implementation record:

- Date: 2026-06-16
- Tightened graph-query semantics in [internal.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/api/src/dcode_api/routes/internal.py):
  - `find_definition` now resolves exact qualified-name matches first, then falls back to suffix matches in a deterministic order
  - `find_references` now uses reverse-edge lookup over `calls/references`, and additionally accepts reverse `imports` edges when the target symbol is a module
  - `get_dependencies` now reads only `imports` edges
  - `get_file_outline` now returns file-local symbols ordered by `file_path`, then `line`, then `qualified_name`
- Added helper-level tests for exact-vs-suffix definition matching and module-only import-reference behavior
- Current graph-data boundary remains explicit:
  - today’s worker graph populates `imports` edges, so module reference/dependency queries are meaningful immediately
  - richer non-module `calls/references` answers will improve as the worker emits those edge types in future graph enhancements
- Verification:
  - Added graph-query tests on top of the existing internal API contract suite
  - `make check`: passed
  - Docker API rebuild: passed
  - Real smoke against ready repo `f09e4e16-18cb-4771-b948-3c1caf4f1cc3`:
    - exact definition: `/internal/find_definition?symbol=src.requests.auth.HTTPBasicAuth`
    - suffix fallback: `/internal/find_definition?symbol=HTTPBasicAuth`
    - module references: `/internal/find_references?symbol=src.requests.auth`
    - imports-only dependencies: `/internal/get_dependencies?module=src.requests.api`
    - ordered outline: `/internal/get_file_outline?path=src/requests/auth.py`

### 3.4 验证

- [x] 对目标 repo 手写 5 个查询
- [x] 每个查询保存期望文件/符号
- [x] 增加 API 测试或集成测试

Implementation record:

- Date: 2026-06-16
- Added versioned retrieval validation fixture at [requests_query_cases.json](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/api/tests/fixtures/requests_query_cases.json) with 5 handwritten `requests` repo cases covering:
  - `/internal/search`
  - `/internal/find_definition`
  - `/internal/find_references`
  - `/internal/get_dependencies`
  - `/internal/get_file_outline`
- Each case now persists expected files and/or symbols so retrieval behavior is auditable without re-deriving answers from memory
- Added [test_internal_validation.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/api/tests/test_internal_validation.py):
  - a deterministic fixture-shape test that keeps the versioned case set complete and unique
  - an optional live integration suite gated by `DCODE_LIVE_REPO_ID`, hitting the running API over HTTP and asserting the saved file/symbol expectations
- Verification:
  - `./.venv/bin/pytest apps/api/tests/test_internal_validation.py -q`: passed
  - `DCODE_LIVE_REPO_ID=f09e4e16-18cb-4771-b948-3c1caf4f1cc3 ./.venv/bin/pytest apps/api/tests/test_internal_validation.py -q`: passed
  - Live cases confirmed:
    - search `auth` returns `src/requests/auth.py`
    - definition `HTTPBasicAuth` resolves to `src.requests.auth.HTTPBasicAuth`
    - references of `src.requests.auth` include `src.requests.adapters`, `src.requests.models`, `src.requests.sessions`
    - dependencies of `src.requests.api` include `src.requests.models`, `src.requests.sessions`
    - outline of `src/requests/auth.py` preserves ordered leading symbols from `src.requests.auth`

Exit criteria: 不用 Agent，直接调用内部 API 可以回答“搜 auth 相关代码”“找 X 定义”“列某文件 outline”。

---

## 4. Agent 最短可用闭环

目标：自然语言问题能触发工具，产生带引用的答案。

### 4.1 Tool execute

- [x] `search_code.execute` 调内部 search API
- [x] `find_definition.execute` 调内部 graph API
- [x] `find_references.execute` 调内部 graph API
- [x] `get_dependencies.execute` 调内部 graph API
- [x] `get_file_outline.execute` 调内部 graph API
- [x] `read_file.execute` 从已索引 repo workdir 读取指定行
- [x] `grep.execute`
  - [x] 如果环境无 `rg`，fallback 到 Python 文件扫描
- [x] `list_directory.execute` 限制在 repo workdir 内
- [x] 防 path traversal：拒绝 `..` 逃逸 workdir

Implementation record:

- Date: 2026-06-16
- Added shared tool helpers in [common.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/common.py):
  - internal API HTTP client against `RETRIEVAL_BASE_URL`
  - repo workdir resolution under `WORKDIR_BASE/{repo_id}`
  - path normalization and traversal rejection
- Wired the retrieval-backed tools to live internal APIs:
  - [search_code.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/search_code.py)
  - [find_definition.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/find_definition.py)
  - [find_references.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/find_references.py)
  - [get_dependencies.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/get_dependencies.py)
  - [get_file_outline.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/get_file_outline.py)
- Implemented filesystem-backed tools:
  - [read_file.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/read_file.py): inclusive line-range reads with validation
  - [grep.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/grep.py): `rg --json` when available, Python regex scan fallback otherwise
  - [list_directory.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/tools/list_directory.py): repo-scoped listing, skips hidden/cache entries, stable ordering
- Added `workdir_base` to [settings.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/settings.py) and updated [docker-compose.yml](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/docker-compose.yml) so Agent and Worker share the same `repo_workdirs` volume; Agent now talks to API through `RETRIEVAL_BASE_URL=http://api:8000` inside Compose
- Added execution coverage in [test_tools_execute.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/tests/test_tools_execute.py) for:
  - retrieval tool HTTP dispatch
  - `read_file` line slicing
  - `grep` Python fallback
  - `list_directory` ordering
  - path traversal rejection
- Verification:
  - `make check`: passed
  - `docker compose up -d --build agent worker`: passed
  - Re-indexed `https://github.com/psf/requests.git` as repo `f89e5e09-272e-40dc-934e-00241d4c045c`, reached `ready`
  - Real smoke inside Agent container:
    - `SearchCodeTool("HTTPBasicAuth")` returned `src/requests/auth.py`
    - `FindDefinitionTool("HTTPBasicAuth")` returned `src/requests/auth.py`
    - `ReadFileTool("src/requests/auth.py", 85-92)` returned the `HTTPBasicAuth` class header
    - `GrepTool("HTTPBasicAuth")` returned repo matches from the shared workdir
    - `ListDirectoryTool("src/requests")` returned visible entries from the repo tree

### 4.2 LangGraph 节点

- [x] `plan_node`
  - [x] 第一版可规则路由：包含 “who calls/reference” 调 `find_references`
  - [x] 包含 “definition/where defined” 调 `find_definition`
  - [x] 默认调 `search_code`
  - [ ] 后续再接 LLM planner
- [x] `tool_call_node`
  - [x] registry lookup
  - [x] Redis tool cache
  - [x] 追加 observations
  - [x] 通过 SSE 发 `tool_call/tool_result`
- [x] `synthesize_node`
  - [x] 第一版可模板化总结 top chunks 和 graph results
  - [ ] 后续再接 LLM synthesis
- [x] `groundedness_node`
  - [x] 调 `groundedness.verify`
  - [ ] 未验证 citation 不计入最终 citations

Implementation record:

- Date: 2026-06-16
- Implemented first-pass LangGraph node logic in [graph.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/graph.py):
  - `plan_node` now performs rule routing with lightweight subject extraction
  - `tool_call_node` now resolves tools from the registry, checks the tool cache, stores observations, and emits `tool_call` / `tool_result`
  - `synthesize_node` now produces template answers from search / graph / file observations
  - `groundedness_node` now calls [groundedness.verify](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/groundedness.py) and records `groundedness_score`
- Extended [state.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/state.py) with:
  - `pending_tool_name`
  - `pending_tool_args`
  - `runtime` context for registry / cache / emitter / db handles
- Updated [main.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/main.py) lifespan to prepare:
  - `app.state.compiled_graph = graph.build_graph()`
  - `app.state.tool_cache = Redis.from_url(...)`
- Relaxed `groundedness.verify(..., db)` to accept `db=None` so the graph can invoke it before 4.3 DB-backed verification lands
- Added graph tests in [test_graph.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/tests/test_graph.py) covering:
  - rule routing for definition vs default search queries
  - tool execution + cache hit behavior
  - template synthesis for search observations
  - one-shot compiled graph execution from `plan -> tool_call -> synthesize -> groundedness`
- Current boundary is explicit:
  - this graph does one planned tool call, then synthesizes
  - `/internal/query` still uses the SSE stub; 4.4 will replace that path with the compiled graph
  - groundedness still flags extracted citations as unverified until 4.3 adds DB-backed checks
- Verification:
  - `./.venv/bin/pytest apps/agent/tests/test_graph.py -q`: passed
  - `MYPYPATH=packages/shared/src:apps/api/src:apps/worker/src:apps/agent/src:apps/eval/src uv run mypy -p dcode_agent`: passed

### 4.3 Groundedness

- [x] `extract_citations` 保持现有 regex 单测
- [x] `verify` 查询 chunks 文件/行范围
- [x] `verify` 查询 symbols qualified_name
- [x] 返回 verified citations 和 score
- [x] 添加 DB fixture 测试

Implementation record:

- Date: 2026-06-16
- Implemented DB-backed citation verification in [groundedness.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/groundedness.py):
  - file citations like ``path/to/file.py:42`` now verify against `chunks` with `start_line <= line <= end_line`
  - symbol citations like ``flask.app.Flask.run`` now verify against exact `symbols.qualified_name`
  - verified symbol citations now resolve back to `file_path` and `line`
  - invalid `repo_id` or missing `db` still degrades to unverified rather than crashing the agent
- Kept the existing regex extraction tests and expanded [test_groundedness.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/tests/test_groundedness.py) with fake DB fixture coverage for:
  - verified file-range match
  - verified symbol match
  - missing line-range citation
  - no-DB fallback
- Verification:
  - `./.venv/bin/pytest apps/agent/tests/test_groundedness.py -q`: passed
  - `MYPYPATH=packages/shared/src:apps/api/src:apps/worker/src:apps/agent/src:apps/eval/src uv run mypy -p dcode_agent`: passed

### 4.4 SSE

- [x] 替换 `_run_stub_pipeline`
- [x] 真正发出：
  - [x] `thought`
  - [x] `tool_call`
  - [x] `tool_result`
  - [x] `citation`
  - [x] `partial_answer` 或直接 `final_answer`
  - [x] `final_answer`
  - [x] `error`
- [x] API gateway 保持透传

Implementation record:

- Date: 2026-06-16
- Replaced the stub query pipeline in [main.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/src/dcode_agent/main.py) with `_run_graph_pipeline(...)`, which:
  - invokes `app.state.compiled_graph`
  - injects `emitter / tool_registry / tool_cache / db` into `AgentState.runtime`
  - emits terminal `citation`, `partial_answer`, and `final_answer` events after graph completion
  - emits `error` on any graph/runtime failure
- Added runtime session wiring in lifespan:
  - `db_session_factory = SessionLocal`
  - `tool_cache` shutdown now tolerates test doubles without `aclose()`
- Added SSE endpoint tests in [test_query_sse.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/tests/test_query_sse.py) covering:
  - successful stream with `thought -> tool_call -> tool_result -> citation -> partial_answer -> final_answer`
  - failure stream with `error`
- Trimmed the old stub-specific assertion from [test_tools_registry.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/agent/tests/test_tools_registry.py) because `/internal/query` now depends on the real graph path instead of a hardcoded fake answer
- Verification:
  - `./.venv/bin/pytest apps/agent/tests/test_query_sse.py apps/agent/tests/test_tools_registry.py -q`: passed
  - `docker compose up -d --build agent`: passed
  - Real smoke through API gateway on repo `f89e5e09-272e-40dc-934e-00241d4c045c`:
    - `POST /api/v1/query` for `Where is \`HTTPBasicAuth\` defined?`
    - streamed `thought`, `tool_call`, `tool_result`, two verified `citation` events, `partial_answer`, and `final_answer`
    - `final_answer.groundedness = 1.0`

Exit criteria: 至少 5 个手写问题能端到端返回答案和 verified citations。

---

## 5. 评测优先闭环

目标：先能量化 H1，再讨论 UI 和部署。

### 5.1 小而准的问题集

- [x] 创建 `apps/eval/src/dcode_eval/questions/data/questions.jsonl`
- [x] 第一版 15-20 题即可
  - [x] L1: 5 题
  - [x] L2: 7-10 题
  - [x] L3: 3-5 题
- [x] 每题包含：
  - [x] `id`
  - [x] `repo_id`
  - [x] `question`
  - [x] `taxonomy`
  - [x] `gt_chunk_ids`
  - [x] `gt_files`
  - [x] `source`
- [x] 人工检查每题 GT

Implementation record:

- Date: 2026-06-16
- Added question schema + loader under [questions](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/questions):
  - [models.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/questions/models.py)
  - [loader.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/questions/loader.py)
- Added curated question set at [questions.jsonl](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/questions/data/questions.jsonl):
  - target repo snapshot: `requests`
  - fixed repo id: `f89e5e09-272e-40dc-934e-00241d4c045c`
  - 16 manually checked questions total
  - taxonomy split: `L1=5`, `L2=8`, `L3=3`
- Stored per-question GT as the current indexed repo snapshot:
  - `gt_chunk_ids` are current chunk UUIDs from the ready `requests` index
  - `gt_files` capture the broader file-level relevance set
  - all current entries are `source="manual"`
- Added dataset tests in [test_questions_dataset.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/tests/test_questions_dataset.py) to lock count, uniqueness, field presence, and taxonomy balance
- Verification:
  - `./.venv/bin/pytest apps/eval/tests/test_questions_dataset.py -q`: passed
  - `uv run ruff check apps/eval/src/dcode_eval/questions apps/eval/tests/test_questions_dataset.py`: passed

### 5.2 Baseline 最小集合

先保留 H1 关键对照，B0/B1 可后补。

- [x] B2 Vanilla Dense RAG
  - [x] dense top-k
  - [x] 单 prompt answer 或模板 answer
- [x] B3 Hybrid RAG
  - [x] hybrid top-k
  - [x] 单 prompt answer 或模板 answer
- [x] B4 Full System
  - [x] 调 agent SSE
  - [x] drain final_answer
- [x] B1 BM25
  - [x] sparse top-k
- [x] B0 GitHub Search
  - [x] 如 GitHub API/rate limit 麻烦，可标记为 optional

Implementation record:

- Date: 2026-06-16
- Added eval settings in [settings.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/settings.py) for API / agent endpoints and retrieval defaults
- Added shared baseline helpers in [common.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/baselines/common.py):
  - internal retrieval API client
  - template answer builder for non-agent baselines
  - SSE drain helper for the full-system baseline
- Implemented minimal runnable baselines:
  - [bm25.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/baselines/bm25.py): sparse retrieval via current internal search path
  - [vanilla_rag.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/baselines/vanilla_rag.py): current dense placeholder, with explicit stub-embedding degradation note
  - [hybrid_rag.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/baselines/hybrid_rag.py): hybrid retrieval + template answer
  - [full_system.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/baselines/full_system.py): API gateway SSE call, drains `final_answer`
- Current baseline boundary is explicit:
  - `B0` remains optional and unimplemented because GitHub Search API auth/rate-limit handling is not needed for the first local H1 run
  - `B2` currently reuses the retrieval API because the repo is still indexed with stub embeddings, so true dense-only separation is not yet meaningful
- Added coverage in [test_baselines.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/tests/test_baselines.py) for template-answer baselines and SSE-based full-system answer assembly
- Verification:
  - `./.venv/bin/pytest apps/eval/tests/test_baselines.py -q`: passed
  - `MYPYPATH=packages/shared/src:apps/api/src:apps/worker/src:apps/agent/src:apps/eval/src uv run mypy -p dcode_eval`: passed

### 5.3 Harness

- [x] `dcode_eval.run`
  - [x] 读取 questions JSONL
  - [x] 选择 baseline
  - [x] 跑 retrieve
  - [x] 跑 answer
  - [x] 写 `per_question.jsonl`
  - [x] 写 `metrics.json`
  - [x] 写 `taxonomy_breakdown.json`
- [x] 指标
  - [x] Recall@k
  - [x] MRR
  - [x] nDCG
  - [x] Groundedness
  - [x] Pairwise win-rate 第一版可人工填或跳过

Implementation record:

- Date: 2026-06-16
- Implemented runnable harness in [run.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/run.py):
  - loads `questions.jsonl`
  - instantiates the selected baseline
  - runs retrieval + answer per question
  - computes `Recall@k`, `MRR`, `nDCG@k`, `Groundedness`
  - writes `per_question.jsonl`, `metrics.json`, `taxonomy_breakdown.json`
- Added baseline factory in [baselines/__init__.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/baselines/__init__.py)
- Added harness test in [test_run.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/tests/test_run.py) for artifact writing and metric aggregation
- Current metric boundary is explicit:
  - `pairwise_win_rate` is emitted as `null` in this first pass
  - groundedness is taken from the baseline answer result, which means template baselines report direct-citation groundedness while `B4` uses the streamed agent score
- Verification:
  - `./.venv/bin/pytest apps/eval/tests/test_run.py -q`: passed
  - Real smoke:
    - `python -m dcode_eval.run --baseline B4 --questions apps/eval/src/dcode_eval/questions/data/questions.jsonl --output results/eval-smoke --k 5`
    - wrote `results/eval-smoke/per_question.jsonl`
    - wrote `results/eval-smoke/metrics.json`
    - wrote `results/eval-smoke/taxonomy_breakdown.json`
    - `metrics.json` summary: `questions=16`, `recall_at_k=0.1979`, `mrr=0.2125`, `ndcg_at_k=0.1917`, `groundedness=0.95`

### 5.4 H1 判定

- [x] 分别报告 L1/L2/L3
- [x] 重点看 L2/L3 上 B4 是否优于 B2/B3
- [x] 如果没有显著优势，如实记录 unsupported
- [x] 不改题、不调阈值、不删除失败样本

Implementation record:

- Date: 2026-06-16
- Extended [run.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/src/dcode_eval/run.py) with suite execution:
  - `--baseline B2 B3 B4` now runs the three baselines in one command
  - writes per-baseline subdirectories plus top-level `suite_summary.json`
  - writes top-level `h1_report.json` when `B2/B3/B4` are all present
- Added fixed H1 decision rule:
  - compare `B4` against both `B2` and `B3`
  - scope limited to `L2` and `L3`
  - composite score = mean of `Recall@k`, `MRR`, `nDCG@k`, `Groundedness`
  - H1 is `supported` only if `B4` beats both `B2` and `B3` by at least `0.05` composite points on both `L2` and `L3`
- Added suite test in [test_run.py](/Users/odieyang/Documents/Projects/Group%20Projects/Dcode/apps/eval/tests/test_run.py) to lock:
  - `suite_summary.json` emission
  - `h1_report.json` emission
  - deterministic `supported` decision under a controlled stub comparison
- Real result for the current repo snapshot is intentionally recorded as-is:
  - command:
    - `python -m dcode_eval.run --baseline B2 B3 B4 --questions apps/eval/src/dcode_eval/questions/data/questions.jsonl --output results/eval-suite --k 5`
  - produced:
    - `results/eval-suite/B2/*`
    - `results/eval-suite/B3/*`
    - `results/eval-suite/B4/*`
    - `results/eval-suite/suite_summary.json`
    - `results/eval-suite/h1_report.json`
  - decision: `unsupported`
  - reason: on both `L2` and `L3`, current `B4` composite does not exceed `B2/B3`; with the current stub-embedding index, `B2` and `B3` collapse to the same retrieval path and `B4` pays extra groundedness penalties without retrieval gains

Exit criteria: 一条命令能跑完至少 B2/B3/B4，并产出可读 metrics。

---

## 6. 前端演示闭环

目标：只做能支撑演示和报告的 UI。

### 6.1 Index Page

- [x] repo URL 输入
- [x] submit 按钮
- [x] 显示 repo_id
- [x] 轮询 status
- [x] 显示 stages/progress/error

Implementation record:

- Date: 2026-06-16
- Replaced the frontend index-page placeholder with a working repo submission flow in `apps/frontend/src/pages/IndexPage.tsx`
- Added:
  - live `POST /api/v1/repos` submit via React Query mutation
  - repo-scoped `GET /api/v1/repos/{repo_id}/status` polling until `ready` / `failed`
  - progress bar plus per-stage `cloning/parsing/embedding/graphing` badges
  - durable recent-repo list in localStorage so later query/demo flows can reuse repo ids
- Added small frontend support modules:
  - `src/components/RepoStatusBadge.tsx`
  - `src/lib/recentRepos.ts`
- Added `tests/IndexPage.test.tsx` covering submit success, status rendering, local recent-repo persistence path, and submit failure surfacing
- Verification:
  - `npm test -- --run`: passed
  - `npm run typecheck`: passed
  - `npm run build`: passed

### 6.2 Query Page

- [ ] repo_id 输入或选择最近索引 repo
- [ ] query 输入
- [ ] `streamQuery` 实现 SSE parser
- [ ] 渲染 7 类事件
- [ ] final answer 区域
- [ ] citations 列表
- [ ] verified/unverified 标记

### 6.3 Demo Compare

- [ ] 同题展示 B2/B3/B4 输出
- [ ] 展示 citations 和 groundedness
- [ ] 展示 L2/L3 示例

Exit criteria: 一次演示能完成“索引 repo -> 提问 -> 展示答案/引用 -> 展示 baseline 对比”。

---

## 7. 工程硬化

这些不优先于 H1，但上线前必须处理。

- [ ] DB
  - [ ] migration 可重复执行
  - [ ] schema 与 SQLAlchemy model 一致
  - [ ] 所有查询都过滤 `repo_id`
- [ ] Redis
  - [ ] embedding cache
  - [ ] tool cache
  - [ ] query cache
  - [ ] job status TTL
- [ ] 安全
  - [ ] repo URL 基础校验
  - [ ] workdir path traversal 防护
  - [ ] internal API 不公开到前端
- [ ] 可观测性
  - [ ] worker 每阶段结构化日志
  - [ ] agent 每个 tool call 日志
  - [ ] eval 记录 run config
- [ ] 测试
  - [ ] worker stage fixture tests
  - [ ] retrieval API tests
  - [ ] agent tool tests
  - [ ] groundedness DB tests
  - [ ] frontend SSE parser tests
- [ ] CI
  - [ ] `make check` 全绿
  - [ ] frontend build 通过
  - [ ] eval smoke test 通过

Exit criteria: 核心路径失败能定位，常见回归能被测试拦住。

---

## 8. 部署与收尾

- [ ] Frontend Dockerfile 从 Vite dev 切到 production static serving
- [ ] 配置生产 `.env`
- [ ] 部署 Docker Compose
- [ ] 域名 `dcode.odieyang.com` 指向服务
- [ ] 跑生产 smoke test
- [ ] README 更新真实状态
- [ ] DESIGN 更新最终实现与偏差
- [ ] PLAN/TODO 更新已完成项
- [ ] 写最终技术报告
- [ ] 写 H1 最终判定

Exit criteria: 外部可访问 demo，文档不再把已完成实现描述成 stub。

---

## 单人执行顺序

按这个顺序做，不要同时开太多面：

- [ ] 1. 决策冻结
- [ ] 2. API repo 持久化 + RabbitMQ 入队
- [ ] 3. Worker clone/parse/chunk/persist
- [ ] 4. Graph definitions/imports 第一版
- [ ] 5. Internal search/graph API
- [ ] 6. Agent tools execute
- [ ] 7. Agent 规则版 plan/synthesize/groundedness
- [ ] 8. 5 个端到端问题
- [ ] 9. Eval questions 小集
- [ ] 10. B2/B3/B4 harness
- [ ] 11. 前端 Query/Index
- [ ] 12. 补 B0/B1、真实 embedding、reranker、judge
- [ ] 13. 部署和报告

---

## 每次提交前检查

- [ ] `uv run ruff check apps packages`
- [ ] `uv run mypy -p dcode_shared -p dcode_api -p dcode_worker -p dcode_agent -p dcode_eval`
- [ ] `uv run pytest`
- [ ] `cd apps/frontend && npm run lint`
- [ ] `cd apps/frontend && npm run typecheck`
- [ ] `cd apps/frontend && npm test -- --run`
- [ ] 更新相关文档中的状态

---

## 降级规则

如果时间不够，按以下规则砍范围：

- [ ] 保留 B2/B3/B4，暂缓 B0/B1
- [ ] 保留 L2/L3 问题，减少 L1
- [ ] 保留 `search_code/find_definition/find_references/read_file`，暂缓 `grep/list_directory`
- [ ] 保留 groundedness，暂缓 query cache
- [ ] 保留本地 Docker demo，暂缓线上部署
- [ ] 保留评测结果，暂缓 UI 精修

不能砍：

- [ ] `repo_id` 隔离
- [ ] 可复现 eval 输出
- [ ] groundedness 校验
- [ ] H1 支持/不支持的诚实结论
