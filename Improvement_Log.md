# Dcode 改进记录（Improvement Log）

> 本文件是 [`problem.md`](problem.md) 中**已完成项**的实现记录（changelog）——从问题登记表拆出，让活跃 backlog 保持精简。每项保留原始诊断 + `✅ 状态`（实现摘要 + 提交号）。
>
> 权威源是 git 历史；本表是人类可读的审计线索。全部改动在分支 `ziqi_review`（PR → `main`）。日期：2026-07-26。

## 已完成一览（15 项）

| ID | 领域 | 提交 | 一句话 |
|---|---|---|---|
| P0-1 | Agent/Groundedness | `95d8972` | groundedness 强制剥离未验证引用 + 阈值可配 |
| P2-1 | Worker/Graph | `67fb694` | 产出 inherits + references 边 |
| P2-3 | Worker/Chunk | `a2318bf` | `ast.unparse` 重建完整多行签名 |
| P2-4 | Worker | `565233d` | 大文件跳过 + 大 chunk 截断 |
| P3-1 | Worker/依赖 | `2a45c4a` | 删死依赖 tree-sitter/jedi + 重锁 |
| P3-2 | API | `7ee4ac7` | 删死代码 `errors.py` |
| P3-3 | Agent/配置 | `ff02fab` | `MAX_STEPS` 去重、可配置 |
| P3-4 | Worker | `267fa74` / `bb7d8bf` | warnings 持久化 + status/前端透出 |
| P3-5 | Eval | `63c32e5` | B4 直连 agent，绕过查询缓存 |
| P3-6 | 文档/图谱 | `cb204d0` / `7a92493` | `dependents` 反向依赖全链路 |
| P3-8 | API | `3427f16` | lifespan 拥有连接生命周期 |
| P3-9 | Worker | `c672f5d` | 失败路径恒不逃逸 ack |
| P3-10 | Frontend | `09e2446` | a11y live region + 去重 + memo |
| P3-11 | Agent | `c404b90` | 工具失败优雅降级 |
| P3-16 | Frontend/测试 | `a311e16` | 修 Node 26 localStorage 测试 |

---

## 详情

### P0-1 ✅ Groundedness "硬护栏 ≥95%" 并未真正强制
- **位置**：`apps/agent/src/dcode_agent/groundedness.py:1-10`（docstring 承诺）、`apps/agent/src/dcode_agent/graph.py:116-131`（`groundedness_node`）。
- **问题**：docstring 明确声称"未验证引用会在返回前被 flagged or stripped""HARD GUARDRAIL，生产环境不可关闭，产出 NFR-4 的 ≥95% 数字"。但实际代码：`verify()` 只计算 `score = verified/total`（无阈值）；`groundedness_node` 只把引用标 `verified=True/False`、记录 `groundedness_score`，然后 `state.final_answer = answer` **原样输出**。全 agent 代码 grep 无任何 `0.95`/阈值/剥离逻辑，也没有任何调用方因低分而阻断。
- **影响**：README 与设计文档把 groundedness 宣传为核心卖点和"硬性验收"，但当前它是**纯记录性**的——一个引用了不存在符号的答案照样会被当作最终答案返回（只是那条引用旁边显示 `verified=false`）。这直接削弱 H1 的"程序化验证引用"论点。
- **✅ 状态（2026-07-26，`95d8972`）**：新增 `enforce_groundedness()`（`apps/agent/src/dcode_agent/groundedness.py`）——始终从 `final_answer` 剥离**所有**未验证引用（backtick 与裸文本两种形式）、仅透出已验证引用；`groundedness_score` 按剥离前计算（诚实反映草稿）；低于阈值时追加 `⚠️` 警告脚注。阈值 `groundedness_threshold`（默认 0.95）加入 `SharedSettings`，并接入 dev/prod `docker-compose` 与 `.env.example`。`groundedness_node`（`graph.py`）接入强制。新增/更新单测覆盖剥离、脚注、仅已验证引用、端到端 grounded 路径。`pytest`（全量）/`ruff`/`mypy --strict` 全绿。

### P2-1 图谱只产 imports + calls，inherits/references 从未生成
- **位置**：`apps/worker/src/dcode_worker/stages/graph.py`（无处读取 `ClassDef.bases`、无引用扫描）；但 `EdgeType.inherits`/`references` 在 `schemas.py:56-63` 与 DB `edge_type` 枚举中都已定义。
- **问题**：schema/文档承诺四类边，实际只落地两类。继承关系、非调用型引用完全缺失。
- **影响**："谁继承了 X""X 在哪被引用"这类结构问题无法回答，削弱结构感知卖点。
- **✅ 状态（2026-07-26，`67fb694`）**：新增 `RelationshipRecord` + `_inherits_for_file`/`_resolve_base`（读 `ClassDef.bases`，解析本地/导入基类）+ `_references_for_file`/`_references_in_body`（函数/方法体内 Load 上下文、排除调用目标与模块引用、按 source→target 去重）+ 通用 `_build_relationship_edges`。**references 立即被 `/internal/find_references` 消费**（其查询本就含 `references`）；**inherits 完成图谱、可直接查库**，专门的子类/父类查询工具留作后续（同 P3-6 dependents 模式）。新增集成 + 单元测试；worker 测试/ruff/mypy 全绿。

### P2-3 chunk 签名只取首行 → 多行函数签名截断
- **位置**：`apps/worker/src/dcode_worker/stages/chunk.py:128`（`_signature` 取 `source_lines[node.lineno-1]`）。
- **问题**：跨多行的 `def foo(\n  a,\n  b,\n):` 只截到第一行，`signature` 字段不完整。
- **✅ 状态（2026-07-26，`a2318bf`）**：`_signature` 改用 `ast.unparse`（不再依赖 `source_lines`）——多行 def/class、注解、默认值、`*args/**kwargs`、返回类型、类基与关键字均完整重建为单行，且与源码换行格式无关。新增多行签名测试；worker 测试/ruff/mypy 全绿。

### P2-4 parse/chunk 无大文件/大类上限
- **位置**：`stages/parse.py`（整文件读入）、`stages/chunk.py`（class chunk = 整个类体）。
- **问题**：超大文件/超大类会被完整读入并作为单个 chunk，随后进 embedding。sidecar 侧虽有 `max_seq_length` 截断，但内存与"一个 chunk 装下整类"的检索粒度问题仍在。
- **✅ 状态（2026-07-26，`565233d`）**：`WorkerSettings.max_file_bytes`（默认 1MB）——parse 用 `stat().st_size` 在**读取前**跳过超大文件并记 warning（经 P3-4 在 GET status 可见）；`max_chunk_chars`（默认 20k）——在唯一出口 `_source_segment` 截断超长 chunk 内容（带 `[truncated]` 标记）。均可用环境变量配置（0 禁用）。新增跳过 + 截断测试；worker 测试/ruff/mypy 全绿。

### P3-1 worker 死依赖：tree-sitter / tree-sitter-python / jedi
- **位置**：`apps/worker/pyproject.toml:8-10`（声明）；`apps/worker/src` grep 零 import；`pyproject.toml` 的 `mypy overrides` 也列了它们。
- **✅ 状态（2026-07-26，`2a45c4a`）**：已从 `apps/worker/pyproject.toml` 和根 `pyproject.toml` 的 mypy overrides 删除；`uv lock` + `make requirements` 已同步移除 `jedi`/`parso`/`tree-sitter(-python)`。worker 测试/ruff/mypy 全绿。

### P3-2 API 死代码 errors.not_implemented
- **位置**：`apps/api/src/dcode_api/errors.py:6`（仅定义，全仓库无调用）。
- **✅ 状态（2026-07-26，`7ee4ac7`）**：已删除整个 `apps/api/src/dcode_api/errors.py`（全仓无引用）。api 测试/ruff/mypy 全绿。

### P3-3 MAX_STEPS 重复且 settings 版本未被读取
- **位置**：`apps/agent/src/dcode_agent/state.py:11`（`MAX_STEPS=8`，被 graph.py 使用）vs `apps/agent/src/dcode_agent/settings.py:9`（`max_steps=8`，无人读）。
- **风险**：两处默认都是 8，一旦有人改 settings 期望生效，实际不会——静默漂移。
- **✅ 状态（2026-07-26，`ff02fab`）**：`graph.py` 改读 `agent_settings.max_steps`，删除 `state.MAX_STEPS` 常量——单一来源、可通过环境变量 `MAX_STEPS` 配置。agent 测试/ruff/mypy 全绿。

### P3-4 worker warnings 收集后从不持久化
- **位置**：`stages/parse.py`（填充 `ctx.warnings`）；`pipeline.py`（从不写出）。
- **问题**：因编码/语法错误被跳过的文件对用户完全不可见。
- **✅ 状态（2026-07-26，`267fa74` + `bb7d8bf`）**：选 Redis `job:{id}` 快照（与 stages 同款 live overlay，无需迁移）——`_job_state_payload` 增加 `warnings`，`handle_job`/`_record_failure` 传入 `ctx.warnings`；`RepoStatusResponse` 新增 `warnings` 字段，`GET status` 经防御式 `_warnings_from` 透出；前端 Index 页渲染琥珀色"N files skipped during parsing"面板。后端 pytest/ruff/mypy 全绿，前端 tsc/eslint 通过。

### P3-5 eval agent_base_url 未接线（对应绕缓存的直连-agent B4 路径）
- **位置**：`apps/eval/src/dcode_eval/settings.py:8`（`agent_base_url`，仅定义、全仓零读取；**不在** `SharedSettings` base，而在 `EvalSettings` 子类）；B4 的 `baselines/common.py:49` 实际 POST 到 `api_base_url` `/api/v1/query`（网关）。
- **重查结论（勿轻删）**：网关 `/api/v1/query` 会把成功结果按 `query:{repo_id}:{hash}` 缓存 1h（`routes/query.py`），命中即回放、不调用 agent。因此当前 B4 走网关**会命中查询缓存**——重跑同一套题时拿到的是缓存旧答案而非 agent 全新运行，污染可复现性（NFR）。`agent_base_url` + agent 的 `/internal/query`（eval 已有 `internal_api_key`/`internal_auth_headers`）恰好能**绕过缓存**做干净测量。git 溯源：与 `api_base_url` 同在初始提交 `37cabb5` 一次性预留，从未接线（"定义 ≠ 有用"，与 P3-3 同类）。
- **✅ 状态（2026-07-26，`63c32e5`）**：采纳方案 A——`stream_full_system_answer` 改打 `agent_base_url` `/internal/query`（带内部鉴权），绕过网关 1h 查询缓存，使每轮 B4 都是 agent 全新运行。`agent_base_url`（默认 `http://localhost:8001`）从死配置变为真功能（运行 eval 需 agent 可达该地址）。新增测试断言走 agent 路径而非网关。eval 测试/ruff/mypy/smoke 全绿。

### P3-6 文档 ↔ 代码漂移（含一个设计了未实现的路由）
- **位置**：`docs/en/Technical_Design.md`（内部 API 曾列 6 条含 `dependents`、`file_context`）vs `apps/api/.../routes/internal.py`；README 的 `chunks` 建表 SQL 缺少实际存在的 `parent_symbol/signature` 等列。
- **重查结论（不只是文档 typo）**：doc 里的 `/internal/dependents`（入向/反向依赖查询）**并非笔误**——迁移 `001` 专门建了反向边索引 `ix_edges_target (repo_id, target_id, edge_type)` 来支撑它，即它是**设计过但未实现**的功能（当时只有出向 `get_dependencies`）。
- **✅ 状态（2026-07-26，`cb204d0` + `7a92493`）**：选择**实现 dependents 全链路**——新增 `/internal/get_dependents` API 路由（`cb204d0`，复用反向索引 `ix_edges_target`）+ agent `get_dependents` 工具与 planner 路由（`7a92493`，注册表 8→9）。同步对齐 `Technical_Design.md` 路由表（6 条，正确名称）与 README chunks 建表（补 `parent_symbol`/`signature`）。api+agent 测试/ruff/mypy 全绿。

### P3-8 no-op lifespan + 惰性模块单例
- **位置**：`apps/api/.../main.py`（lifespan 空转）、`deps.py`（redis/httpx 惰性单例，`TODO(M2)`）。
- **问题**：首个请求承担连接建立开销，与 NFR TTFB≤3s 相悖；连接生命周期未随 app 管理。
- **✅ 状态（2026-07-26，`3427f16`）**：API lifespan 新增 `warm_pools`/`close_pools`——启动时实例化并拥有 Redis + agent httpx 客户端、关闭时释放；`get_*` 保留惰性兜底（测试不受影响）。`get_db` 本就用共享 SQLAlchemy 引擎池；agent 服务已在其 lifespan 管理 Redis。**未纳入（有意）**：RabbitMQ 仍按发布连接（提交路径；`connect_robust` 启动预连接会使 boot 变脆）、`routes/internal.py` 的 query embedding/reranker 惰性客户端（仅真实模型模式命中）。新增 lifespan 生命周期测试。

### P3-9 worker 失败路径可逃逸"总是 ack"
- **位置**：`apps/worker/src/dcode_worker/pipeline.py`（except 分支内 `_update_repo` 若 repo 行缺失会 `RuntimeError`）。
- **问题**：正常路径靠吞异常 + `message.process()` 实现"总是 ack、失败不重投"。但若 repo 行不存在（例如被删），失败处理里的持久化会再抛错并逃出 `handle_job` → 消息被 nack/重投 → 可能无限重投同一坏消息。
- **✅ 状态（2026-07-26，`c672f5d`）**：新增 `RepoRowMissingError`——成功路径遇它良性丢弃（repo 已删 → ack + warn）；失败持久化抽成 `_record_failure` 并用 try/except 兜底（repo 缺失或 PG 挂都只记日志不抛）。`handle_job` 对可解析消息恒不抛异常，"总是 ack / 不重投"不变量成立。新增两条逃逸路径测试。

### P3-10 前端无障碍与小瑕疵
- **位置**：`apps/frontend/src/pages/QueryPage.tsx`（流式事件区无 `aria-live`）、`src/api/client.ts:49`（过期 TODO：所述 SSE 解析其实下方已实现）、`toKnownRepoStatus` 在 IndexPage/QueryPage 重复、`finalAnswer/partialAnswer` 每次 render 反转数组未 memo。
- **✅ 状态（2026-07-26，`09e2446`）**：final-answer 区加 `aria-live="polite"`、event-stream 加 `role="log"`+`aria-live`；`toKnownRepoStatus` 抽到 `@/lib/repoStatus`（Index/Query 共用）；`finalAnswer/partialAnswer/citations` 改 `useMemo`；`client.ts` 过期 TODO 改写为准确文档。tsc/eslint/vitest/build 全绿。

### P3-11 agent 图的 error 边不可达
- **位置**：`graph.py`（`decide_after_plan` 与 `tool_call` 条件边读 `state.error`）；但**任何节点都不写** `state.error`，工具异常直接 bubble 到 `main.py` 转成 SSE error。
- **✅ 状态（2026-07-26，`c404b90`）**：`tool_call_node` 经新增的 `_record_tool_failure` 捕获工具异常（无效 args / 检索·图 API / 文件系统），写 `state.error` 并发 `error:` 的 tool_result；已有条件边据此路由到 synthesize，`synthesize_node` 前置 `⚠️` 失败提示。原先不可达的 error 边现已激活。新增降级测试；agent 测试/ruff/mypy 全绿。

### P3-16 前端 vitest 在 Node 26 下整体失败（localStorage）
- **位置**：`apps/frontend/tests/setup.ts`；症状为 `QueryPage.test.tsx` / `IndexPage.test.tsx` 的 `beforeEach` 里 `window.localStorage.clear()` 抛 `Cannot read properties of undefined`。
- **问题**：Node 26 引入实验性原生 `localStorage`（需 `--localstorage-file` 才启用），在 jsdom 环境下遮蔽了 DOM Storage，使 `window.localStorage` 变为 `undefined`。CI 用 Node 20 不受影响，故只在较新本机复现（本轮做 P3-4 前端时发现，已用 stash 证明与业务改动无关）。
- **✅ 状态（2026-07-26，`a311e16`）**：在 `tests/setup.ts` 安装确定性的内存版 `Storage`（`defineProperty` 到 `window` + `globalThis`），版本无关且改善测试隔离。前端 vitest 现 8/8 通过，tsc/eslint/build 全绿。
