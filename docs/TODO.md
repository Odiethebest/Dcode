# Dcode TODO

> 基于骨架阶段（M0）的工作清单与决策记录。**最后更新：2026-06-10**。
>
> 关联文档：[DESIGN.md](DESIGN.md)（技术细节）、[PLAN.md](PLAN.md)（时间线 + RACI + 风险）、[Structure.md](Structure.md)（文件结构）。

---

## 骨架自验证状态（M0）

| # | 项 | 状态 |
|---|---|---|
| 1 | `docker compose up -d --build` 全 7 服务 healthy | ✅ agent / api / frontend / postgres / rabbitmq / redis / worker |
| 2 | `make migrate` Alembic migration 001 干净施加 | ✅ `repos / chunks / symbols / edges` + `pg_extension vector` |
| 3 | `make check` 全绿 | ✅ ruff 0 / mypy --strict 58 文件 / pytest 32 passed / eslint 0 / tsc 0 / vitest 2 passed |
| 4 | `curl POST /api/v1/repos` 202 + 正确 body shape | ✅ `{"repo_id":"<uuid>","status":"queued"}` |
| 5 | `curl GET /api/v1/repos/{id}/status` 200 + 正确 shape | ✅ `{repo_id, status, progress, stages:{4个}, error}` |
| 6 | `curl POST /api/v1/query` SSE 推 stub thought + final_answer 并关闭 | ✅ 标准 §4.3 wire format |

**16 个 commits**，**~105 source files**（不含 vendor / venv）。

---

## M1 — 数据通路打通 (W1)

**Exit Criteria** (PLAN.md §7.1)：目标仓库经索引管线完整写入数据库；DESIGN §3 数据模型冻结；§4.1 接口冒烟测试通过。

### Worker / 索引管线
- [ ] **`apps/worker/src/dcode_worker/stages/clone.py:run`** — `git clone --depth=1 ctx.repo_url <workdir>`，设置 `ctx.workdir`
- [ ] **`apps/worker/src/dcode_worker/stages/parse.py:run`** — 递归 .py → tree-sitter Python grammar → 填 `ctx.files` + AST roots
- [ ] **`apps/worker/src/dcode_worker/stages/chunk.py:run`** — 按函数 / 方法 / 类 / 模块 docstring 边界切（**D-2.1.1 禁定长滑窗**）；每个 chunk 含 file_path / symbol_name / signature / start_line / end_line / imports / content
- [ ] **`apps/worker/src/dcode_worker/stages/graph.py:run`** — jedi 解析 def / ref / imports / inherits；填 `ctx.symbols` + `ctx.edges`
- [ ] **`apps/worker/src/dcode_worker/pipeline.py:handle_job`** — 解 message → 推进 Repo.status（**D-2.1.4 monotonic state machine**）→ 调每个 stage → 持久化 chunks/symbols/edges → 更新 Redis `job:{repo_id}` 进度

### API
- [ ] **`apps/api/src/dcode_api/routes/repos.py:submit_repo`** — 真持久化 Repo 行 + 发布 RabbitMQ 任务到 `dcode.index_jobs`
- [ ] **`apps/api/src/dcode_api/routes/repos.py:repo_status`** — 从 DB 读 Repo + 从 Redis 读 `job:{repo_id}` 进度

### 决策 / 风险
- [ ] **OD-1**：选 requests / flask / fastapi 一个作为主目标（**W1 周一前**，Odie）
- [ ] **R-4 验证**：jedi 在选定 repo 的解析覆盖率抽测（**W1 周末前**）

---

## M2 — 端到端可问答 (W2)

**Exit Criteria** (PLAN.md §7.1)：§2.2、§2.3 完成；至少 5 个示例问题端到端产出带引用的答案；§4.2、§4.3 冻结。

### Worker / Embedding
- [ ] **`apps/worker/src/dcode_worker/stages/embed.py:run`** — 实现完整流程：
  1. 每 chunk 算 `embed:{model_id}:{sha256(content)}` 缓存 key
  2. Redis mget 命中部分
  3. batch-embed miss 通过 OD-2 模型客户端
  4. mset 新向量（TTL 永久）
  5. 写 `chunks.embedding` 列
- [ ] **OD-2 决策**：jina-code / bge-code / voyage-code 抽测后选定（W1 周三前，P2 Yuxin）

### Retrieval & Graph API（DESIGN.md §4.2 — 目前不存在）
- [ ] 决定新建独立 retrieval 服务 OR 在 api 加内部路由：
  - `GET /internal/search?repo_id=&query=&k=` → ranked `Chunk[]`（dense + sparse + RRF k=60 + cross-encoder rerank）
  - `GET /internal/find_definition?repo_id=&symbol=` → `Location[]`
  - `GET /internal/find_references?repo_id=&symbol=` → `Location[]`
  - `GET /internal/get_dependencies?repo_id=&module=` → `Module[]`
  - `GET /internal/get_file_outline?repo_id=&path=` → `Symbol[]`
- [ ] **OD-3 决策**：reranker 自托管 bge-reranker vs Cohere API（W1 周末前，P2 Yuxin）

### Agent / LangGraph 节点
- [ ] **`apps/agent/src/dcode_agent/graph.py:plan_node`** — planner LLM：输入 query + observations + tool manifest；输出下一个 tool_call 或 synthesize 信号
- [ ] **`apps/agent/src/dcode_agent/graph.py:tool_call_node`** — registry.get(name) → Redis cache lookup → execute → 更新 observations → step_count++
- [ ] **`apps/agent/src/dcode_agent/graph.py:synthesize_node`** — synthesis LLM 用 observations 产 `draft_answer` + 候选 citations
- [ ] **`apps/agent/src/dcode_agent/graph.py:groundedness_node`** — 调 `groundedness.verify`；标记 unverified；写 `final_answer` + `groundedness_score`
- [ ] **`apps/agent/src/dcode_agent/main.py`** — 替换 `_run_stub_pipeline` 为 `app.state.compiled_graph.ainvoke(state)`；节点完成时通过 SSEEmitter 发对应事件
- [ ] **`apps/agent/src/dcode_agent/groundedness.py:verify`** — 真 SELECT against `chunks (repo_id, file_path)` + `symbols (repo_id, qualified_name)`；返回 `GroundednessResult.score`

### Agent / 8 个 Tool 的 execute
- [ ] **`search_code.execute`** — POST `/internal/search`
- [ ] **`read_file.execute`** — 读 repo workdir 内文件指定行范围
- [ ] **`find_definition.execute`** / **`find_references.execute`** / **`get_dependencies.execute`** / **`get_file_outline.execute`** — 调对应 `/internal/*` 端点
- [ ] **`grep.execute`** — subprocess `rg --json -n <pattern> <workdir>` → parse 到 Location
- [ ] **`list_directory.execute`** — `os.scandir(workdir / args.path)`

### API
- [ ] **`apps/api/src/dcode_api/routes/query.py`** — 加 `query:{repo_id}:{query_hash}` 缓存层（DESIGN.md §3.3，TTL 1h）

### Frontend
- [ ] **`apps/frontend/src/api/client.ts:streamQuery`** — fetch + ReadableStream 解 SSE 帧（`event:` / `data:` 行）→ 调 caller-supplied handler
- [ ] **`apps/frontend/src/pages/QueryPage.tsx`** — 输入框 + 7 类事件渲染器 + 引用跳转
- [ ] **`apps/frontend/src/pages/IndexPage.tsx`** — 提交输入 + 轮询 / SSE 索引状态
- [ ] **`apps/frontend/src/api/types.ts`** — 切到 `openapi-typescript` 自动生成（删手工 mirror）

---

## M3 — 评测可复现 (W3)

**Exit Criteria** (PLAN.md §7.1)：B0–B4 全部跑完至少一轮；指标产出符合 §4.4 格式；UI 主路径可用。

### 问题集
- [ ] **`apps/eval/src/dcode_eval/questions/data/questions.jsonl`** — 50–80 题，三源混合：
  - 20–50 题人工标注（含 L1/L2/L3 taxonomy 标签）
  - 30–50 题函数反向合成
  - 部分 GitHub issue / commit 挖掘
- [ ] **OD-4 决策**：Judge 模型选定（W1 周末前，P3 Yufan）
- [ ] **R-2 验证**：20 题人工 vs Judge 相关性抽测；< 0.6 改用 pairwise + 人工兜底

### Baselines
- [ ] **B0** `github_search.py` — GET `https://api.github.com/search/code?q=<q> repo:<o/n>`
- [ ] **B1** `bm25.py` — retrieval API 的 BM25 子路径
- [ ] **B2** `vanilla_rag.py` — pgvector cosine top-k → 单 prompt LLM
- [ ] **B3** `hybrid_rag.py` — retrieval API hybrid → 单 prompt LLM（无 agent 循环）
- [ ] **B4** `full_system.py` — POST agent `/internal/query` → drain SSE → 组 AnswerResult

### 指标
- [ ] **`apps/eval/src/dcode_eval/metrics/judge.py:Judge`** 客户端实现（score + pairwise）
- [ ] **`apps/eval/src/dcode_eval/metrics/groundedness.py:GroundednessChecker`** 实现（调 agent verify 或本地复制 regex 提取）

### Harness
- [ ] **`apps/eval/src/dcode_eval/run.py`** — 迭代 questions × baselines → 聚合 → 写 §4.4 落盘：
  ```
  results/{run_id}/
    ├── config.json
    ├── per_question.jsonl
    ├── metrics.json
    └── taxonomy_breakdown.json
  ```

### Frontend
- [ ] 对比演示视图（完整系统 vs 裸 RAG 并列，P1 功能）

---

## M4 — 上线 + 收尾 (W4)

- [ ] **部署 `dcode.odieyang.com`**（OD-5 已闭环）
- [ ] **Frontend production build** — 替换 dev server Dockerfile 为 nginx 静态托管
- [ ] **最终评测 + H1 判定** — 达标 / 不达标 如实记录
- [ ] **技术报告 / 博客 / 架构图**
- [ ] **README 的「快速开始」「项目结构」从 TBD 填实际**

---

## M0 自作主张的决定（未在 DESIGN / PLAN 中明确）

| # | 决定 | 理由 |
|---|---|---|
| 1 | ORM = **SQLAlchemy 2.0 async**（非 SQLModel） | hybrid 检索涉 pgvector + tsvector 自定义算子，纯 SQLAlchemy 更灵活 |
| 2 | 队列客户端 = **aio-pika** | TDD §7 首选 RabbitMQ；aio-pika 是 asyncio 原生主流客户端 |
| 3 | 前端服务端状态 = **TanStack Query** | 骨架阶段无客户端全局状态；TanStack 处理 SSE/轮询/缓存够用 |
| 4 | Python workspace = **uv + Hatch backend** | uv workspaces 当下主流；Hatch backend 简洁 |
| 5 | Node 包管理 = **npm**（非 pnpm） | 兼容性最广，CI 零额外安装步骤 |
| 6 | **Agent 作为独立 FastAPI 服务**（非嵌入 API） | 匹配 DESIGN.md §2.2 架构图；API 用 httpx SSE-proxy 到 `/internal/query`；扩展 / 部署解耦 |
| 7 | 新增 **`apps/worker/src/dcode_worker/context.py`** | 打破 `pipeline.py` ↔ `stages/*.py` 的循环 import |
| 8 | 新增 **`apps/agent/src/dcode_agent/{sse,state}.py`** | 状态机 state 与 SSE 队列发射器从 main.py 拆出来，便于 M2 替换 |
| 9 | Agent `/internal/tools` manifest 端点 | 调试 + planner LLM 可直接读 |
| 10 | **`metrics/retrieval.py` 写真实现**（不 stub） | Recall@k / MRR / nDCG 是纯数学，写出来比 stub 短；单测覆盖率高 |
| 11 | 所有 5 个包加 **`py.typed`** | PEP 561 strict mypy 必需 |
| 12 | Pytest **`pythonpath` 显式列 5 个 src dir** | 本地 venv Python 3.14 不消化 uv 生成的 `.pth` 文件（似 site.py 行为变化）|
| 13 | **删 `apps/*/tests/__init__.py`** | 多个 `tests` 顶级包名冲突；pytest 推荐 tests dir 不 packagize |
| 14 | **ruff B008 全局 ignore** | FastAPI `Depends()` 作 default arg 是项目最常见模式 |
| 15 | **Frontend healthcheck 用 `127.0.0.1`** | 容器内 `localhost` 命中 IPv6 `::1`，Vite 仅绑 IPv4 |
| 16 | `tsconfig.json` 加 `node` 到 types；加 `@types/node` | `vite.config.ts` 用了 `node:path` / `process.env` / `__dirname` |
| 17 | **`tool.uv.dev-dependencies` → `dependency-groups.dev`** | uv 0.11+ 弃用旧 key |

---

## 留给人决策的问题（M0 后）

1. **`apps/agent` 长期是独立服务还是收回 API？** — M0 拍"独立"；M2 验证后再评估
2. **Frontend production 部署形态** — 当前 Dockerfile 是 dev 版（`npm run dev`）；M4 切静态构建（nginx）还是保 Node SSR？
3. **Alembic env.py 用 psycopg2-binary** — Python 3.14 上 psycopg2 渐疲态，是否换 `psycopg[binary]` 3.x？现在不痛，可延后
4. **测试覆盖率门槛** — CI 当前不强制；M2 是否加 `pytest --cov --fail-under=N`？
5. **ruff 规则集** — 当前 `E, F, I, N, UP, B, C4, SIM`；是否加 `RUF` / `PL` / `ANN`？

---

## 对 TDD 既有决策的质疑（仅记录，未擅自变更）

| 项 | TDD 立场 | 我的疑虑 |
|---|---|---|
| Agent 最大步数 = 8 | §2.3.1 | L3 架构级问题可能需 10+ 步；建议 M3 跑评测后回看；可能要分等级（L1=4 / L2=6 / L3=10）|
| Reranker RRF k=60 | §2.2.1 | k=60 是文献起点而非金标；M2 实测时拉曲线再定 |
| `chunk_type` 仅 4 种（function / method / class / module_doc）| §3.2 | 大模块顶层赋值、装饰器、TypedDict 等可能需额外类型；M1 看真实 repo 再扩 |
