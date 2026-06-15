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

- [ ] `apps/worker/src/dcode_worker/pipeline.py`
  - [ ] 解析 message body
  - [ ] 按顺序推进状态：`queued -> cloning -> parsing -> embedding -> graphing -> ready`
  - [ ] 任一阶段异常时写 `failed` 和 `error`
  - [ ] 每阶段更新 Redis `job:{repo_id}`
  - [ ] 最终提交 DB transaction
- [ ] 明确失败策略
  - [ ] clone 失败直接 failed
  - [ ] 单文件 parse 失败先跳过并记录 warning
  - [ ] graph 部分失败不阻断 chunks 落库

### 2.3 Clone / Parse / Chunk

- [ ] `stages/clone.py`
  - [ ] 使用 `git clone --depth=1`
  - [ ] workdir 按 repo_id 隔离
  - [ ] 记录 commit SHA
- [ ] `stages/parse.py`
  - [ ] 递归收集 `.py` 文件
  - [ ] 跳过 `.venv`、`venv`、`.git`、`__pycache__`、build artifacts
  - [ ] 用 tree-sitter 或 Python `ast` 产出可供 chunk 使用的结构
- [ ] `stages/chunk.py`
  - [ ] 函数 chunk
  - [ ] method chunk
  - [ ] class chunk
  - [ ] module docstring chunk
  - [ ] 提取 `file_path/symbol_name/signature/start_line/end_line/imports/content`
  - [ ] 禁止定长滑窗
- [ ] 测试
  - [ ] 用 2-3 个小 fixture 文件覆盖 function/class/method/docstring
  - [ ] 验证 line number 准确
  - [ ] 验证 imports 随 chunk 带上

### 2.4 Embedding 第一版

- [ ] `stages/embed.py`
  - [ ] 先接 `StubEmbeddingClient` 让 DB 能完整写入
  - [ ] 实现 `embed:{model_id}:{sha256(text)}` 缓存 key
  - [ ] 实现 Redis `mget/mset`
  - [ ] embedding 维度与 `EMBEDDING_DIM` 一致
- [ ] 后续替换真实模型时保持接口不变

### 2.5 Graph 第一版

- [ ] `stages/graph.py`
  - [ ] 先用 AST 提取 definitions，填 `symbols`
  - [ ] imports 边先做到模块级
  - [ ] calls/references 可先粗略提取，再用 jedi 增强
  - [ ] 每个 symbol 尽量关联 `chunk_id`
- [ ] 测试
  - [ ] fixture 里验证 function/class/module symbols
  - [ ] 验证 imports edge
  - [ ] 验证 repo_id 隔离

Exit criteria: 一个真实目标 repo 能从 API 提交，经 worker 写入 DB；`chunks` 和 `symbols` 有非空数据；`make check` 通过。

---

## 3. 检索与图查询闭环

目标：不经过 Agent，直接用内部 API 找到相关代码。

### 3.1 内部 Retrieval API

- [ ] 决定位置：优先放在 `apps/api/src/dcode_api/routes/internal.py`
- [ ] 新增内部接口：
  - [ ] `GET /internal/search?repo_id=&query=&k=`
  - [ ] `GET /internal/find_definition?repo_id=&symbol=`
  - [ ] `GET /internal/find_references?repo_id=&symbol=`
  - [ ] `GET /internal/get_dependencies?repo_id=&module=`
  - [ ] `GET /internal/get_file_outline?repo_id=&path=`
- [ ] 所有查询必须带 `repo_id`
- [ ] 所有返回使用 `dcode_shared.schemas`

### 3.2 Search 第一版

- [ ] sparse 检索
  - [ ] 使用 `tsv` 或简单 SQL fallback
  - [ ] 支持精确 symbol/path 命中
- [ ] dense 检索
  - [ ] stub embedding 阶段允许退化
  - [ ] 真实 embedding 后使用 pgvector cosine
- [ ] fusion
  - [ ] 实现 RRF
  - [ ] score_components 保留 dense/sparse/rerank
- [ ] rerank
  - [ ] 第一版可设为 identity rerank
  - [ ] 正式评测前接真实 reranker

### 3.3 Graph Queries

- [ ] `find_definition`
  - [ ] exact qualified_name
  - [ ] suffix match fallback
- [ ] `find_references`
  - [ ] reverse edge lookup
  - [ ] calls/references 都考虑
- [ ] `get_dependencies`
  - [ ] imports edge lookup
- [ ] `get_file_outline`
  - [ ] 按 file_path 和 line 排序 symbols

### 3.4 验证

- [ ] 对目标 repo 手写 5 个查询
- [ ] 每个查询保存期望文件/符号
- [ ] 增加 API 测试或集成测试

Exit criteria: 不用 Agent，直接调用内部 API 可以回答“搜 auth 相关代码”“找 X 定义”“列某文件 outline”。

---

## 4. Agent 最短可用闭环

目标：自然语言问题能触发工具，产生带引用的答案。

### 4.1 Tool execute

- [ ] `search_code.execute` 调内部 search API
- [ ] `find_definition.execute` 调内部 graph API
- [ ] `find_references.execute` 调内部 graph API
- [ ] `get_dependencies.execute` 调内部 graph API
- [ ] `get_file_outline.execute` 调内部 graph API
- [ ] `read_file.execute` 从已索引 repo workdir 读取指定行
- [ ] `grep.execute`
  - [ ] 如果环境无 `rg`，fallback 到 Python 文件扫描
- [ ] `list_directory.execute` 限制在 repo workdir 内
- [ ] 防 path traversal：拒绝 `..` 逃逸 workdir

### 4.2 LangGraph 节点

- [ ] `plan_node`
  - [ ] 第一版可规则路由：包含 “who calls/reference” 调 `find_references`
  - [ ] 包含 “definition/where defined” 调 `find_definition`
  - [ ] 默认调 `search_code`
  - [ ] 后续再接 LLM planner
- [ ] `tool_call_node`
  - [ ] registry lookup
  - [ ] Redis tool cache
  - [ ] 追加 observations
  - [ ] 通过 SSE 发 `tool_call/tool_result`
- [ ] `synthesize_node`
  - [ ] 第一版可模板化总结 top chunks 和 graph results
  - [ ] 后续再接 LLM synthesis
- [ ] `groundedness_node`
  - [ ] 调 `groundedness.verify`
  - [ ] 未验证 citation 不计入最终 citations

### 4.3 Groundedness

- [ ] `extract_citations` 保持现有 regex 单测
- [ ] `verify` 查询 chunks 文件/行范围
- [ ] `verify` 查询 symbols qualified_name
- [ ] 返回 verified citations 和 score
- [ ] 添加 DB fixture 测试

### 4.4 SSE

- [ ] 替换 `_run_stub_pipeline`
- [ ] 真正发出：
  - [ ] `thought`
  - [ ] `tool_call`
  - [ ] `tool_result`
  - [ ] `citation`
  - [ ] `partial_answer` 或直接 `final_answer`
  - [ ] `final_answer`
  - [ ] `error`
- [ ] API gateway 保持透传

Exit criteria: 至少 5 个手写问题能端到端返回答案和 verified citations。

---

## 5. 评测优先闭环

目标：先能量化 H1，再讨论 UI 和部署。

### 5.1 小而准的问题集

- [ ] 创建 `apps/eval/src/dcode_eval/questions/data/questions.jsonl`
- [ ] 第一版 15-20 题即可
  - [ ] L1: 5 题
  - [ ] L2: 7-10 题
  - [ ] L3: 3-5 题
- [ ] 每题包含：
  - [ ] `id`
  - [ ] `repo_id`
  - [ ] `question`
  - [ ] `taxonomy`
  - [ ] `gt_chunk_ids`
  - [ ] `gt_files`
  - [ ] `source`
- [ ] 人工检查每题 GT

### 5.2 Baseline 最小集合

先保留 H1 关键对照，B0/B1 可后补。

- [ ] B2 Vanilla Dense RAG
  - [ ] dense top-k
  - [ ] 单 prompt answer 或模板 answer
- [ ] B3 Hybrid RAG
  - [ ] hybrid top-k
  - [ ] 单 prompt answer 或模板 answer
- [ ] B4 Full System
  - [ ] 调 agent SSE
  - [ ] drain final_answer
- [ ] B1 BM25
  - [ ] sparse top-k
- [ ] B0 GitHub Search
  - [ ] 如 GitHub API/rate limit 麻烦，可标记为 optional

### 5.3 Harness

- [ ] `dcode_eval.run`
  - [ ] 读取 questions JSONL
  - [ ] 选择 baseline
  - [ ] 跑 retrieve
  - [ ] 跑 answer
  - [ ] 写 `per_question.jsonl`
  - [ ] 写 `metrics.json`
  - [ ] 写 `taxonomy_breakdown.json`
- [ ] 指标
  - [ ] Recall@k
  - [ ] MRR
  - [ ] nDCG
  - [ ] Groundedness
  - [ ] Pairwise win-rate 第一版可人工填或跳过

### 5.4 H1 判定

- [ ] 分别报告 L1/L2/L3
- [ ] 重点看 L2/L3 上 B4 是否优于 B2/B3
- [ ] 如果没有显著优势，如实记录 unsupported
- [ ] 不改题、不调阈值、不删除失败样本

Exit criteria: 一条命令能跑完至少 B2/B3/B4，并产出可读 metrics。

---

## 6. 前端演示闭环

目标：只做能支撑演示和报告的 UI。

### 6.1 Index Page

- [ ] repo URL 输入
- [ ] submit 按钮
- [ ] 显示 repo_id
- [ ] 轮询 status
- [ ] 显示 stages/progress/error

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
