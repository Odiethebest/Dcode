# Dcode Skeleton Structure

> 骨架阶段 (M0) 的详细文件结构，标注每个文件的职责、stub 状态、对应里程碑。**最后更新：2026-06-10**。
>
> 关联文档：[DESIGN.md](DESIGN.md) 是 § 编号的权威来源；[PLAN.md](PLAN.md) 给出里程碑定义；[TODO.md](TODO.md) 列出尚未实现的工作。
>
> 图例：**Real** = 实际可用；**Skeleton** = 形状完整但函数体 `raise NotImplementedError`；**M1/M2/M3/M4** = 该工作所属里程碑。

---

## 总览

```
dcode/
├── (workspace root + orchestration + docs)
├── packages/shared/   跨服务唯一事实源（schemas / models / events / cache keys）
├── apps/api/          FastAPI gateway (port 8000) — 公开入口
├── apps/worker/       RabbitMQ 消费者，跑索引管线
├── apps/agent/        独立 FastAPI agent 服务 (port 8001)
├── apps/eval/         离线评测 harness (CLI)
├── apps/frontend/     Vite + React 18 + TS SPA (port 5173)
├── infra/             Dockerfile + Alembic + Postgres 初始化
├── scripts/           本地开发 shell 辅助
└── .github/           CI workflow
```

7 个 Docker 服务，编排在 `docker-compose.yml`。所有跨服务类型由 `packages/shared` 唯一定义。**前端永不直连 agent 或 DB**——只通过 `/api/v1/*`。

---

## 1. Workspace 根

| 文件 | 职责 | 状态 |
|---|---|---|
| `pyproject.toml` | uv workspace 根（5 members）；ruff / mypy / pytest 全局配置 | Real |
| `Makefile` | `up / down / logs / ps / check / lint / typecheck / test / migrate / fmt / smoke / clean` | Real |
| `docker-compose.yml` | 7 服务 + healthcheck + 1 named volume | Real |
| `.env.example` | 全部 env 变量；OD-2..OD-4 占位注释 | Real |
| `.gitignore` | Python / Node / OS / IDE / env / `*.tsbuildinfo` | Real |
| `uv.lock` | 锁定依赖版本（committed） | Real |
| `LICENSE` | Apache 2.0 | Real |
| `README.md` | 公开门面（badges / ToC / arch / API ref / decisions / team） | Real |
| `docs/{DESIGN,PLAN,Kick_off,TODO,Structure}.md` | 项目文档体系 | Real |

---

## 2. `packages/shared/` — 跨服务事实源

对应 DESIGN.md §3（数据模型）+ §4（接口契约）。**其他服务 import 这里的类，禁止自行定义**。

```
packages/shared/
├── pyproject.toml                     hatch package；deps: pydantic, sqlalchemy[asyncio], asyncpg,
│                                                              pgvector, redis
├── src/dcode_shared/
│   ├── __init__.py                    package metadata
│   ├── py.typed                       PEP 561 typed-package marker (空文件)
│   ├── schemas.py            ★Real    所有 Pydantic models per §4 (RepoCreateRequest /
│   │                                  RepoCreateResponse / RepoStatusResponse / StagesStatus /
│   │                                  QueryRequest / Chunk / Location / ScoreComponents) +
│   │                                  6 个 StrEnum (RepoStatus / StageState / ChunkType /
│   │                                  SymbolKind / EdgeType + ChunkType)
│   ├── events.py             ★Real    7 SSE 事件类型 (ThoughtEvent / ToolCallEvent /
│   │                                  ToolResultEvent / CitationEvent / PartialAnswerEvent /
│   │                                  FinalAnswerEvent / ErrorEvent) + sse_encode wire helper
│   ├── cache.py              Real     embedding_cache_key / tool_cache_key / query_cache_key /
│   │                                  job_state_key + _hash_args；严格按 §3.3 命名
│   ├── settings.py           Real     SharedSettings (pydantic-settings) — database_url /
│   │                                  redis_url / rabbitmq_url / log_level + OD-2..OD-4 占位
│   └── db/
│       ├── __init__.py                re-exports Base / Repo / Chunk / Symbol / Edge / engine /
│       │                              SessionLocal
│       ├── models.py         ★Real    SQLAlchemy 2.0 declarative：repos / chunks / symbols / edges
│       │                              （4 个 Postgres ENUM type；Vector(EMBEDDING_DIM) 列；
│       │                              TSVECTOR 列；FK 全部按 §3.2 表设计）
│       └── session.py        Real     async engine (asyncpg) + async_sessionmaker +
│                                      get_session() FastAPI dependency
└── tests/
    └── test_schema_roundtrip.py       7 tests：roundtrip / shape / cache keys / SSE wire format
```

---

## 3. `apps/api/` — Gateway (port 8000)

```
apps/api/
├── pyproject.toml                     deps: fastapi, uvicorn, httpx, aio-pika, alembic,
│                                              psycopg2-binary, dcode-shared
├── src/dcode_api/
│   ├── __init__.py
│   ├── py.typed                       PEP 561 marker
│   ├── main.py               Real     FastAPI app；CORS middleware；/healthz；router 挂载；
│   │                                  lifespan stub (M2 warm pools)
│   ├── settings.py           Real     APISettings extends SharedSettings；
│   │                                  cors_origins (逗号分隔字符串 → list) + agent_url
│   ├── deps.py               Real     get_db / get_redis / get_agent_client；M2 改用
│   │                                  lifespan-managed pools
│   ├── errors.py             Real     not_implemented(milestone, ref) — 501 helper
│   └── routes/
│       ├── __init__.py                empty
│       ├── repos.py          Skeleton POST /api/v1/repos (202 + uuid stub) +
│       │                              GET /api/v1/repos/{id}/status (shape stub) — **M1 真持久化**
│       └── query.py          Real★    POST /api/v1/query → httpx.stream() SSE-proxy 到
│                                      agent /internal/query；agent 不可达时降级发 stub thought
└── tests/
    └── test_health.py                 3 tests：/healthz / POST /repos 202 shape /
                                       GET /status shape
```

**Architectural note**: API 是唯一公开服务，agent 网络隔离在 `/internal/*`。前端只通过 `/api/v1/*` 通信。

---

## 4. `apps/worker/` — RabbitMQ consumer

```
apps/worker/
├── pyproject.toml                     deps: aio-pika, tree-sitter, tree-sitter-python, jedi,
│                                             redis, dcode-shared
├── src/dcode_worker/
│   ├── __init__.py
│   ├── py.typed                       PEP 561 marker
│   ├── main.py               Real     consume_loop()：aio_pika.connect_robust →
│   │                                  channel.declare_queue(dcode.index_jobs, durable) →
│   │                                  消费循环 + ack；signal-safe shutdown
│   ├── settings.py           Real     WorkerSettings (workdir_base, queue_name)
│   ├── context.py            ★Real    PipelineContext dataclass — **新增文件**，
│   │                                  打破 pipeline ↔ stages 循环 import
│   ├── pipeline.py           Skeleton handle_job(message_body)：解 JSON → 校验 →
│   │                                  日志记录；M1 实现状态机推进 + 持久化
│   └── stages/                        **每个 stage 一个文件，签名固定：
│       │                              async def run(ctx: PipelineContext) -> PipelineContext**
│       ├── __init__.py                re-exports
│       ├── clone.py          M1       git clone --depth=1 ctx.repo_url → ctx.workdir
│       ├── parse.py          M1       tree-sitter walk → ctx.files (含 AST roots)
│       ├── chunk.py          M1       AST 级切块 (D-2.1.1) → ctx.chunks (function / method /
│       │                              class / module_doc)
│       ├── embed.py          ★Real/M2 **EmbeddingClient ABC + StubEmbeddingClient (Real)；
│       │                              run() 实现 M2**；OD-2 swap-point
│       └── graph.py          M1       jedi def/ref/imports/inherits → ctx.symbols + ctx.edges
└── tests/
    └── test_pipeline_skeleton.py      4 tests：ctx default / all stages importable /
                                       handle_job tolerates malformed / stub embed dim
```

**Architectural note**: 状态机 **D-2.1.4 单调推进**（`queued → cloning → parsing → embedding → graphing → ready`）在 `pipeline.handle_job` 实现（M1）。`stages/*.py` 是纯函数：拿 ctx，返回 ctx，不持流程状态。

---

## 5. `apps/agent/` — Agent Orchestrator (port 8001) ★

**User M0 阶段重点关注层**。独立 FastAPI 服务，API gateway 通过 `httpx.AsyncClient.stream()` SSE-proxy 进来。

```
apps/agent/
├── pyproject.toml                     deps: fastapi, uvicorn, langgraph, httpx, redis,
│                                             dcode-shared
├── src/dcode_agent/
│   ├── __init__.py
│   ├── py.typed                       PEP 561 marker
│   ├── main.py               Real     /healthz + /internal/tools (manifest) +
│   │                                  /internal/query (SSE)；lifespan 装配 tool_registry；
│   │                                  目前 /internal/query 跑 _run_stub_pipeline (M2 换 graph)
│   ├── settings.py           Real     AgentSettings (max_steps=8, retrieval_base_url)
│   ├── state.py              ★Real    AgentState dataclass + MAX_STEPS=8 (§2.3.1) —
│   │                                  **新增文件**
│   ├── sse.py                ★Real    SSEEmitter：asyncio.Queue + 7 typed emit_* methods +
│   │                                  iter_bytes() — **新增文件**
│   ├── graph.py              ★Skel/M2 LangGraph StateGraph：plan → tool_call → decide →
│   │                                  synthesize → groundedness_check → END；
│   │                                  4 个节点 raise NotImplementedError；decide_next() Real
│   ├── groundedness.py       ★Real    extract_citations (regex 提取 file:line + qualified name)
│   │                                  Real；verify() M2 真 SELECT (D-2.3.1 硬 guardrail)
│   └── tools/                ★        **8 个 tool 各一文件，统一 Tool[ArgsT, ResultT] generic**
│       ├── __init__.py                default_registry() — 注册全部 8 个
│       ├── base.py           Real     Tool ABC + ToolRegistry；name / description /
│       │                              ArgsSchema 模板字段；cache_key 用 §3.3 命名
│       ├── search_code.py    Skel/M2  hybrid 检索 (调 retrieval API)
│       ├── read_file.py      Skel/M2  按行范围读
│       ├── find_definition.py Skel/M2 符号定义位置
│       ├── find_references.py Skel/M2 反向边查询（who calls X）
│       ├── get_dependencies.py Skel/M2 module imports 图
│       ├── get_file_outline.py Skel/M2 文件内符号列表
│       ├── grep.py           Skel/M2  ripgrep 精确符号搜索
│       └── list_directory.py Skel/M2  文件系统导航
└── tests/
    ├── test_tools_registry.py         6 tests：8 tools / args schema / cache key /
    │                                  healthz / manifest / SSE thought event
    └── test_groundedness.py           3 tests：file:line regex / qualified-name regex /
                                       empty case
```

**Agent 数据流**：

```
POST /internal/query
   ↓
SSEEmitter() + AgentState(repo_id, query)
   ↓
asyncio.create_task(_run_stub_pipeline)   ←  M2 替换为 graph.build_graph().ainvoke()
   ↓
emitter.iter_bytes()
   ↓
StreamingResponse → API gateway → 前端
```

**Tool 抽象**：

```python
class Tool(ABC, Generic[ArgsT, ResultT]):
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    ArgsSchema: ClassVar[type[BaseModel]] = BaseModel

    @abstractmethod
    async def execute(self, repo_id: str, args: ArgsT) -> ResultT: ...

    def cache_key(self, repo_id: str, args: ArgsT) -> str:
        return tool_cache_key(self.name, repo_id, args.model_dump(mode="json"))
```

每个子类：
- `name` / `description` / `ArgsSchema` 三个类变量（registry 用作 manifest）
- 实现 `execute(repo_id, args) -> ResultT`
- `cache_key()` 自动用 `tool:{name}:{repo_id}:{hash}` 命名

M2 加 Redis 缓存包装层在 `tool_call_node` 内：

```python
key = tool.cache_key(repo_id, args)
if cached := await redis.get(key):
    return Result.model_validate_json(cached)
result = await tool.execute(repo_id, args)
await redis.setex(key, 86400, result.model_dump_json())  # TTL 24h per D-2.3.2
return result
```

---

## 6. `apps/eval/` — Evaluation Harness

```
apps/eval/
├── pyproject.toml                     deps: httpx, dcode-shared；
│                                              entry: dcode-eval = dcode_eval.run:main
├── src/dcode_eval/
│   ├── __init__.py
│   ├── py.typed                       PEP 561 marker
│   ├── run.py                Skel/M3  argparse CLI：--baseline B0..B4 --questions --output；
│   │                                  当前打印意图，M3 实迭代 + 聚合 + 写盘
│   ├── baselines/
│   │   ├── __init__.py                re-exports
│   │   ├── base.py           Real     Baseline ABC + AnswerResult dataclass；
│   │   │                              retrieve() + answer() 两个抽象方法
│   │   ├── github_search.py  Skel/M3  B0 — GitHub code search API
│   │   ├── bm25.py           Skel/M3  B1 — sparse 检索
│   │   ├── vanilla_rag.py    Skel/M3  B2 — 单路 dense + LLM
│   │   ├── hybrid_rag.py     Skel/M3  B3 — hybrid 检索 + LLM（无 agent 循环）
│   │   └── full_system.py    Skel/M3  B4 — 调 agent /internal/query
│   ├── metrics/
│   │   ├── __init__.py                re-exports retrieval functions
│   │   ├── retrieval.py      ★Real    **recall_at_k / mrr / ndcg_at_k 真实现，不是 stub**；
│   │   │                              纯数学；test 覆盖 6 个 edge case
│   │   ├── judge.py          Real/M3  Judge ABC + StubJudge (OD-4 swap-point) +
│   │   │                              JudgeScore + PairwiseVerdict
│   │   └── groundedness.py   Real/M3  GroundednessChecker ABC + GroundednessRow
│   └── questions/
│       └── README.md         Real     问题集构造说明 + JSONL schema；M3 在 data/ 下放真实集
└── tests/
    └── test_metrics_skeleton.py       9 tests：5 baseline ids / Recall / MRR / nDCG edge cases
```

**Decision**: `metrics/retrieval.py` 写真实现（不 stub）—— 这些是纯数学，写出来比 stub 短，且每个函数都有单测覆盖。

---

## 7. `apps/frontend/` — SPA (port 5173)

```
apps/frontend/
├── package.json                       React 18 / Router v6 / TanStack Query v5 / Tailwind 3 /
│                                       Vitest 1 / typescript-eslint v8 / eslint 9
├── package-lock.json                  committed
├── tsconfig.json                      strict: true；baseUrl + @/* alias；
│                                       types: [node, vite/client, vitest/globals, jest-dom]
├── vite.config.ts                     React plugin；dev proxy /api → API gateway；
│                                       Vitest 配置嵌入 (jsdom + globals)
├── eslint.config.js                   flat config: js.recommended + typescript-eslint v8 +
│                                       react-hooks；argsIgnorePattern '^_'
├── tailwind.config.ts                 content: index.html + src/**/*.{ts,tsx}
├── postcss.config.js                  tailwindcss + autoprefixer
├── .prettierrc.json                   singleQuote, trailingComma es5, 100 cols
├── index.html                         #root + main.tsx
├── src/
│   ├── main.tsx              Real     QueryClientProvider + BrowserRouter + StrictMode
│   ├── App.tsx               Real     nav shell + Routes (Index / Query)
│   ├── index.css             Real     @tailwind base/components/utilities
│   ├── pages/
│   │   ├── IndexPage.tsx     Skel/M2  仓库提交 + 索引状态展示 placeholder
│   │   └── QueryPage.tsx     Skel/M2  聊天 + SSE 渲染 placeholder
│   ├── api/
│   │   ├── types.ts          Real★    手工 mirror of dcode_shared.schemas（M2 →
│   │   │                              openapi-typescript 自动生成）
│   │   └── client.ts         Real/M2  submitRepo + getRepoStatus (Real)；
│   │                                  streamQuery (M2 SSE consumer)
│   └── components/.gitkeep            空 dir，M2 加 UI 组件
└── tests/
    ├── setup.ts                       @testing-library/jest-dom matchers
    └── App.test.tsx                   2 tests：nav links / lands on Index
```

**前后端隔离纪律**：

1. 前端只通过 `src/api/client.ts` 与 `/api/v1/*` 对话
2. 类型来源：当前手工 mirror `types.ts` ↔ `dcode_shared.schemas.py`；M2 切到 `openapi-typescript` 自动生成
3. CORS：API 服务通过 `CORS_ORIGINS` env 配置允许的 origin
4. 部署：`VITE_API_BASE_URL` env 决定 API base；dev 时 Vite proxy 转发 `/api`

---

## 8. `infra/`

```
infra/
├── docker/
│   ├── api.Dockerfile        Real     python:3.11-slim + uv + COPY 全 workspace + uv sync；
│   │                                  CMD uvicorn (port 8000)
│   ├── worker.Dockerfile     Real     python:3.11-slim + uv + COPY workspace；
│   │                                  CMD python -m dcode_worker.main
│   ├── agent.Dockerfile      Real     python:3.11-slim + ripgrep + uv + COPY workspace；
│   │                                  CMD uvicorn (port 8001)
│   └── frontend.Dockerfile   Real     node:20-alpine + COPY apps/frontend + npm install；
│                                       CMD npm run dev (M4 换 nginx 静态)
├── migrations/
│   ├── alembic.ini           Real     script_location = infra/migrations
│   ├── env.py                Real     使用 dcode_shared.db.models.Base.metadata；
│   │                                  +asyncpg → +psycopg2 swap (alembic 同步驱动)
│   └── versions/
│       └── 001_initial_schema.py  ★Real  4 表 + 4 ENUM + pgvector extension + HNSW + GIN +
│                                  反向边索引（DESIGN.md §3.2 逐字）
└── postgres/
    └── init.sql              Real     CREATE EXTENSION IF NOT EXISTS vector
                                       (Postgres 容器首次启动时运行一次)
```

**Dockerfile pattern**: 每个 Python 服务 COPY 完整 workspace（uv workspace 解析需要所有 members），但 `--package <name>` CMD 只跑指定服务。镜像大小代价 < 共享 lock 收益。

---

## 9. `scripts/` + `.github/`

```
scripts/
├── dev-up.sh                 Real    一键起 stack + 跑 migration + 打印 URL（chmod +x）
└── seed.sh                   Skel/M1 M1 后填 sample repo URLs / test questions（chmod +x）

.github/workflows/
└── ci.yml                    Real    2 jobs：
                                       - python: uv sync → ruff → mypy (-p mode) → pytest
                                       - frontend: npm install → eslint → tsc -b --noEmit →
                                         vitest --run
```

---

## 横切关注点

### 多租户隔离 (NFR-3)

所有 `chunks` / `symbols` / `edges` / jobs 按 `repo_id` 隔离。SQLAlchemy 模型每张表都有 FK 到 `repos`。Redis key 命名 (`tool:{name}:{repo_id}:{hash}`) 也按 repo_id 分桶。Schema-level 保证。

### 缓存 (DESIGN.md §3.3)

| 模式 | 用途 | TTL |
|---|---|---|
| `embed:{model_id}:{sha256(text)}` | embedding 缓存 | 永久 (content-addressed) |
| `tool:{name}:{repo_id}:{hash}` | 工具结果缓存 | 24h |
| `query:{repo_id}:{hash}` | 完整查询缓存 | 1h |
| `job:{repo_id}` | 索引任务状态 | 任务完成后 7d |

Helper 函数全部在 `packages/shared/src/dcode_shared/cache.py`。**严禁**业务代码内嵌 key 字符串拼接。

### SSE 协议 (DESIGN.md §4.3)

7 类事件 (`thought` / `tool_call` / `tool_result` / `citation` / `partial_answer` / `final_answer` / `error`) 定义在 `packages/shared/src/dcode_shared/events.py`。`sse_encode(event, data)` 是唯一 wire-format 入口。

| 角色 | 工具 |
|---|---|
| **Agent** 发射 | `SSEEmitter` (asyncio.Queue 后端，typed `emit_*()` 方法) |
| **API** 转发 | `httpx.stream(...).aiter_bytes()` 透传 |
| **Frontend** 消费 | `fetch` + `ReadableStream` 按 `\n\n` 切帧 (M2 实现) |

### Open Decision 占位策略

| OD | env var | 默认值 | 何处替换 |
|---|---|---|---|
| OD-2 (embedding model) | `EMBEDDING_MODEL` + `EMBEDDING_DIM` | `stub` / `1024` | `apps/worker/src/dcode_worker/stages/embed.py:EmbeddingClient` |
| OD-3 (reranker) | `RERANKER_ENDPOINT` | `http://localhost:9999` | retrieval API (M2 新建) |
| OD-4 (judge) | `JUDGE_MODEL` | `stub` | `apps/eval/src/dcode_eval/metrics/judge.py:Judge` |

OD-1 (target repo) 和 OD-5 (域名) 不进 env，由 README / 部署配置承载。

### 端口分配

| 服务 | 容器内 | 主机映射 |
|---|---|---|
| Postgres | 5432 | 5432 |
| Redis | 6379 | 6379 |
| RabbitMQ AMQP | 5672 | 5672 |
| RabbitMQ Management UI | 15672 | 15672 |
| API gateway | 8000 | 8000 |
| Agent | 8001 | 8001 |
| Frontend (Vite dev) | 5173 | 5173 |
