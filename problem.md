# Dcode 问题清单与改进路线（Problem Register）

> 目的：把当前实现与 Dcode 设计目标（尤其是 **H1 假设**）之间的差距，整理成一份可执行、可拆成 issue/PR 的问题登记表，用于全面提升项目质量。
>
> 生成日期：2026-07-26 ｜ 依据：对全仓库（`packages/shared` + 6 个服务 + 前端 + infra + docs）的通读。
> 标 ✅ 的问题已直接在源码中核实过（非推断）。
>
> **更新 2026-07-26**（同步 `origin/main`@`4710602`，PR #10）：已并入「加权 RRF 融合」——混合检索由 1:1 等权改为 **dense:sparse = 2:1**（`RRF_DENSE_WEIGHT`/`RRF_SPARSE_WEIGHT`，tie-break 改 dense 优先；见 `apps/api/src/dcode_api/routes/internal.py` `_fuse_search_candidates`）。该改动**只在真实 embedding 下生效**（stub 下 dense 返回空、权重为零），不改变下列任何问题的成立性。

## 如何阅读

- **优先级**：`P0`(完整性/误导，最高) → `P1`(H1 可信度，项目核心使命) → `P2`(能力缺口) → `P3`(技术债/漂移/健壮性/无障碍/运维)。
- **类型**：`缺陷`=行为错误或误导；`缺口`=已规划但未实现（多为 M2/M3）；`债务`=可运行但不干净/易漂移。
- **工作量**：`S`≈半天内 ｜ `M`≈1–3 天 ｜ `L`≈>3 天或需先设计。

---

## 概览表

| ID | 优先级 | 类型 | 领域 | 一句话 | 工作量 |
|---|---|---|---|---|---|
| ~~P0-1~~ | P0 | 缺陷 | Agent/Groundedness | ✅**已修复**：groundedness 现强制剥离未验证引用 + 仅透出已验证引用 + 阈值可配 | M |
| P0-2 | P0 | 缺陷 | Eval | 已提交的 `results/eval-suite/` 快照早于当前代码，误导性 ✅ | S |
| P1-1 | P1 | 缺口 | Eval/模型 | 默认全 stub 模型 → H1 无法真实测量，B2=B3=B4 指标相同 | M |
| P1-2 | P1 | 缺口 | Eval/Judge | LLM-as-Judge 是 stub → pairwise win-rate 恒为 None | M |
| P1-3 | P1 | 缺口 | Eval/数据集 | 仅 16 题、单一仓库、无统计显著性（固定 0.05 阈值启发式） | L |
| P1-4 | P1 | 缺口 | Agent | 规划与合成为规则驱动/模板拼接，非 LLM → H1 的"agent"臂偏弱 | L |
| P2-1 | P2 | 缺口 | Worker/Graph | 图谱只产 imports+calls；schema 定义的 inherits/references 从未生成 | M |
| P2-2 | P2 | 缺口 | Worker | 仅索引 Python | L |
| ~~P2-3~~ | P2 | 缺陷 | Worker/Chunk | ✅**已修复**（`a2318bf`）：改用 `ast.unparse` 重建完整签名 | S |
| P2-4 | P2 | 缺陷 | Worker | parse/chunk 无大文件上限 → 内存/token 爆炸风险 | S |
| P2-5 | P2 | 缺口 | Agent/SSE | `partial_answer` 整段一次性发出，非逐 token 流式 | M |
| ~~P3-1~~ | P3 | 债务 | Worker/依赖 | ✅**已修复**（`2a45c4a`）：删除死依赖 + 重新锁定 | S |
| ~~P3-2~~ | P3 | 债务 | API | ✅**已修复**（`7ee4ac7`）：删除死代码 `errors.py` | S |
| ~~P3-3~~ | P3 | 债务 | Agent/配置 | ✅**已修复**（`ff02fab`）：去重，改为读 `AgentSettings.max_steps` | S |
| P3-4 | P3 | 缺陷 | Worker | `ctx.warnings`（跳过的文件）收集后从不持久化 → 用户看不到 | S |
| P3-5 | P3 | 缺口 | Eval/可复现性 | `agent_base_url` 未接线，但对应"绕网关查询缓存、直连 agent"的 B4 路径（勿轻删） | S |
| P3-6 | P3 | 债务/缺口 | 文档漂移 | 命名/schema 漂移 + `dependents`（入向依赖）是设计了未实现（反向索引已建） | S/M |
| P3-7 | P3 | 缺口 | API/安全 | 公开 `/api/v1/*` 无客户端鉴权（M2） | M |
| P3-8 | P3 | 债务 | API/Agent | no-op lifespan + 惰性模块单例（DB/Redis/httpx 未连接池预热，M2） | M |
| ~~P3-9~~ | P3 | 缺陷 | Worker | ✅**已修复**（`c672f5d`）：`RepoRowMissingError` 良性丢弃 + 失败持久化兜底，`handle_job` 恒不抛 | S |
| P3-10 | P3 | 缺陷 | Frontend/无障碍 | 流式区无 `aria-live`；过期 TODO；`toKnownRepoStatus` 重复；派生态未 memo | S |
| ~~P3-11~~ | P3 | 债务 | Agent | ✅**已修复**（`c404b90`）：工具失败写 `state.error`，图内优雅降级 | S |
| P3-12 | P3 | 债务 | Frontend | 类型手动镜像后端 schema → 应改 OpenAPI 代码生成（M2） | M |
| P3-13 | P3 | 缺口 | 可观测性 | 无 tracing/metrics；LangGraph 无 checkpointer（graph.py:160 TODO） | M |
| P3-14 | P3 | 缺口 | 运维/部署 | `dcode.odieyang.com` 未解析；生产 compose 仅本地验证 | M |
| P3-15 | P3 | 缺口 | 测试 | 全部靠注入 fake，无真实 PG/Redis/RabbitMQ 的集成/端到端测试 | M |

---

## P0 — 完整性问题（正在误导使用者/评审者）

### P0-1 ✅ Groundedness "硬护栏 ≥95%" 并未真正强制
- **位置**：`apps/agent/src/dcode_agent/groundedness.py:1-10`（docstring 承诺）、`apps/agent/src/dcode_agent/graph.py:116-131`（`groundedness_node`）。
- **问题**：docstring 明确声称"未验证引用会在返回前被 flagged or stripped""HARD GUARDRAIL，生产环境不可关闭，产出 NFR-4 的 ≥95% 数字"。但实际代码：`verify()` 只计算 `score = verified/total`（无阈值）；`groundedness_node` 只把引用标 `verified=True/False`、记录 `groundedness_score`，然后 `state.final_answer = answer` **原样输出**。全 agent 代码 grep 无任何 `0.95`/阈值/剥离逻辑，也没有任何调用方因低分而阻断。
- **影响**：README 与设计文档把 groundedness 宣传为核心卖点和"硬性验收"，但当前它是**纯记录性**的——一个引用了不存在符号的答案照样会被当作最终答案返回（只是那条引用旁边显示 `verified=false`）。这直接削弱 H1 的"程序化验证引用"论点。
- **建议修复**：
  1. 在 `groundedness_node` 增加真正的强制：低于阈值（如 0.95）时，从 `final_answer` 中**删除或降级**未验证的 `file:line`/符号引用，并在答案中标注"已移除 N 条未验证引用"。
  2. 阈值做成可配置（`SharedSettings.groundedness_threshold`，默认 0.95），但生产不可为 0。
  3. 若达不到阈值，考虑发一个 `error` 或在 `final_answer` 里显式声明置信度下降。
  4. 补一个断言"低分答案会被剥离"的单测。
- **工作量**：M。
- **✅ 状态（2026-07-26 已实现）**：新增 `enforce_groundedness()`（`apps/agent/src/dcode_agent/groundedness.py`）——始终从 `final_answer` 剥离**所有**未验证引用（backtick 与裸文本两种形式）、仅透出已验证引用；`groundedness_score` 按剥离前计算（诚实反映草稿）；低于阈值时追加 `⚠️` 警告脚注。阈值 `groundedness_threshold`（默认 0.95）加入 `SharedSettings`，并接入 dev/prod `docker-compose` 与 `.env.example`。`groundedness_node`（`graph.py`）接入强制。新增/更新单测覆盖剥离、脚注、仅已验证引用、端到端 grounded 路径。`pytest`（全量）/`ruff`/`mypy --strict` 全绿。

### P0-2 ✅ 已提交的评测快照早于当前代码，具误导性
- **位置**：`results/eval-suite/{B2,B3,B4}/`、`results/eval-suite/{suite_summary,h1_report}.json`。
- **问题**：各 baseline 子目录**只有** `metrics.json / per_question.jsonl / taxonomy_breakdown.json`，**缺 `run_config.json`**——而当前 `run.py:44` 每次运行都会写 `run_config.json`（`test_run.py` 也断言了）。快照日期为 6 月 16 日，B4 答案文本（"Top code hits for…"、引用测试文件）既不符合当前 `template_answer` 也不符合 SSE 路径。README 直接引用了这些数字作为"当前 H1 结论"。
- **影响**：README/`H1_Decision.md`/前端 Compare 页展示的都是过期结果；任何人据此判断 H1 都是基于失效数据。
- **建议修复**：在真实 sidecar（Jina 768 + BGE reranker）下重新索引目标仓库并重跑 `run_suite`，覆盖 `results/eval-suite/`，同步更新 README §Current Result、`H1_Decision.md`、`Final_Report.md` 和前端 `evalSnapshot.ts`。在结果目录补 `run_config.json`（记录模型配置 + commit + 问题集）。
- **在途**：未合并分支 `feat/b0-github-search`（`fb86626`）已在真实 Jina embedding 下刷新过 eval-suite，可作覆盖来源；但需先并入加权 RRF（PR #10，已在 main）后重跑，并补齐 `run_config.json`。
- **工作量**：S（重跑）；依赖 P1-1（真实模型可用）。

---

## P1 — H1 可信度（项目存在的根本目的）

> H1 是本项目**唯一的可证伪目标**。当前状态下 H1 无法被诚实测量，这是"全面提升项目"的第一优先方向。

### P1-1 默认全 stub 模型 → H1 无法真实测量
- **位置**：`.env.example`（`EMBEDDING_MODEL=stub`/`RERANKER_MODEL=stub`）、`packages/shared/.../settings.py:39-48`。
- **问题**：stub embedding 返回全零向量 → dense 检索无结果 → hybrid 退化为 sparse；stub reranker = 恒等排序。因此 **B2(dense)=B3(hybrid)=B4** 检索指标完全相同（快照里 Recall@5 均为 0.198）。H1 想比较的正是 dense/hybrid/图谱带来的增量，stub 下这些增量结构性地为零。
- **影响**：H1 记录为 unsupported 主要是 stub 的必然产物，而非假设本身被证伪。
- **建议修复**：把"真实模型评测"制度化：按 `docs/en/Sidecar_Smoke.md` 起 embedding(768)+reranker sidecar，`down-all && migrate` 重建 768 维库，重索引 `requests`，再跑 B0–B4。产出对比"stub 基线"与"真实模型"两份结果。
- **在途/相关**：`origin/main`（PR #10）已加入加权 RRF（dense:sparse=2:1），但 **stub 下 dense 返回空、权重完全不生效**——只有真实模型才让 B2/B3/B4 分化。未合并分支 `feat/b0-github-search`（`fb86626`, 2026-07-12）已用真实 Jina embedding 刷新过 eval-suite（提交信息："B1/B2/B3/B4 now distinct"），可作为本项起点；但它早于加权 RRF（2026-07-21），合并后需重跑。
- **工作量**：M。

### P1-2 LLM-as-Judge 是 stub → 无法产出 pairwise win-rate
- **位置**：`apps/eval/src/dcode_eval/metrics/judge.py`（`StubJudge` 返回全 0 + "tie"）、`run.py:154,164`（`pairwise_win_rate` 硬编码 `None`）。
- **问题**：README 的验收阈值之一是"vs Vanilla RAG 的 pairwise win-rate > 60%"，但 judge 从未实现，win-rate 永远是 `None`。四个答案质量维度（correctness/completeness/faithfulness/actionability）也无人评分。
- **建议修复**：实现一个真实 `Judge`（OD-4），用 Claude 做成对比较与四维打分；接入 `run_suite` 计算 win-rate 并写入 `suite_summary.json`。注意 judge 需固定 prompt/温度以保证可复现（NFR）。
- **工作量**：M。

### P1-3 问题集过小、单仓库、无统计显著性
- **位置**：`apps/eval/src/dcode_eval/questions/data/questions.jsonl`（16 题，全 `requests`）、`run.py:179-225`（H1 判定）。
- **问题**：① 仅 16 题（README 目标 50–80），且全部来自单一仓库、`source` 全为 `manual`；② H1"显著性"只是一个固定绝对阈值启发式（B4−B2≥0.05 且 B4−B3≥0.05），**无 p 值/置信区间/bootstrap/配对检验**；③ 缺 README 承诺的"函数反向合成 + GitHub issue 挖掘"两种问题来源与标注协议、hold-out 子集。
- **影响**：即使真实模型下 B4 领先，也难以主张"统计显著"。样本量太小，方差主导结论。
- **建议修复**：扩到 50–80 题、覆盖 ≥2 个仓库、混合三种构造来源；把 H1 判定升级为配对 bootstrap 或置换检验并报告置信区间；文档化标注协议与 hold-out。
- **工作量**：L。

### P1-4 Agent 规划/合成为规则驱动，非 LLM
- **位置**：`apps/agent/src/dcode_agent/graph.py`（`_select_initial_tool` 关键词路由、`_synthesize_*` 模板拼接）。
- **问题**：H1 主张的是"**工具化 agent 编排**"的增益，但当前 planner 是子串关键词路由、synthesis 是字符串模板拼接，全程无 LLM（`main.py` 里"planner LLM"只是注释）。这是有意的基础集成路径，但它让 B4 相对 B3 的"agent 增量"几乎只剩多跳检索，答案本身没有推理生成。
- **影响**：B4 与 H1 想验证的"agent orchestration"存在实现-目标落差；模板答案也拉低 judge 质量分。
- **建议修复**：引入 LLM 规划（工具选择/参数）与 LLM 合成（基于工具观测生成带引用的答案），保留 groundedness 作为后置校验。规则路径可保留为降级模式。这是把 B4 做成"真·全系统"的关键。
- **工作量**：L。

---

## P2 — 能力缺口

### P2-1 图谱只产 imports + calls，inherits/references 从未生成 ✅
- **位置**：`apps/worker/src/dcode_worker/stages/graph.py`（无处读取 `ClassDef.bases`、无引用扫描）；但 `EdgeType.inherits`/`references` 在 `schemas.py:56-63` 与 DB `edge_type` 枚举中都已定义。
- **问题**：schema/文档承诺四类边，实际只落地两类。继承关系、非调用型引用完全缺失。
- **影响**："谁继承了 X""X 在哪被引用"这类结构问题无法回答，削弱结构感知卖点。
- **建议修复**：新增 pass 读取 `ClassDef.bases` 生成 `inherits` 边；对符号名做引用扫描生成 `references` 边。补图谱阶段单测。
- **工作量**：M。

### P2-2 仅索引 Python
- **位置**：`stages/parse.py`（只 `rglob *.py` + stdlib `ast`）。
- **问题**：非 Python 仓库无法索引。README/文档也已声明此边界。
- **建议修复**：中长期引入语言无关解析（此处 `tree-sitter` 依赖终于有了用武之地——见 P3-1），先支持 JS/TS。
- **工作量**：L。

### P2-3 chunk 签名只取首行 → 多行函数签名截断
- **位置**：`apps/worker/src/dcode_worker/stages/chunk.py:128`（`_signature` 取 `source_lines[node.lineno-1]`）。
- **问题**：跨多行的 `def foo(\n  a,\n  b,\n):` 只截到第一行，`signature` 字段不完整。
- **建议修复**：用 `node.lineno..node.body[0].lineno-1`（或 `ast.get_source_segment` 到冒号）拼完整签名。
- **工作量**：S。
- **✅ 状态（2026-07-26，`a2318bf`）**：`_signature` 改用 `ast.unparse`（不再依赖 `source_lines`）——多行 def/class、注解、默认值、`*args/**kwargs`、返回类型、类基与关键字均完整重建为单行，且与源码换行格式无关。新增多行签名测试；worker 测试/ruff/mypy 全绿。

### P2-4 parse/chunk 无大文件/大类上限
- **位置**：`stages/parse.py`（整文件读入）、`stages/chunk.py`（class chunk = 整个类体）。
- **问题**：超大文件/超大类会被完整读入并作为单个 chunk，随后进 embedding。sidecar 侧虽有 `max_seq_length` 截断，但内存与"一个 chunk 装下整类"的检索粒度问题仍在。
- **建议修复**：加文件字节上限（跳过并记 warning）与超长 chunk 的二次切分；把跳过项通过 P3-4 暴露给用户。
- **工作量**：S。

### P2-5 partial_answer 整段一次性发出，非流式
- **位置**：`apps/agent/src/dcode_agent/main.py:122-123`。
- **问题**：SSE 协议支持逐 token，但当前把完整答案作为单个 `partial_answer` 发出，失去流式体验、TTFB 无改善。
- **建议修复**：接入 LLM 合成（P1-4）后按 token/句子分块 emit `partial_answer`。
- **工作量**：M（与 P1-4 绑定）。

---

## P3 — 技术债 / 文档漂移 / 健壮性 / 无障碍 / 运维

### P3-1 ✅ worker 死依赖：tree-sitter / tree-sitter-python / jedi
- **位置**：`apps/worker/pyproject.toml:8-10`（声明）；`apps/worker/src` grep 零 import；`pyproject.toml` 的 `mypy overrides` 也列了它们。
- **建议修复**：要么删除（当前解析 100% 用 stdlib `ast`），要么在实现 P2-2 多语言时真正启用。先删，需要时再加，避免误导依赖体积。
- **工作量**：S。
- **✅ 状态（2026-07-26，`2a45c4a`）**：已从 `apps/worker/pyproject.toml` 和根 `pyproject.toml` 的 mypy overrides 删除；`uv lock` + `make requirements` 已同步移除 `jedi`/`parso`/`tree-sitter(-python)`。worker 测试/ruff/mypy 全绿。

### P3-2 ✅ API 死代码 errors.not_implemented
- **位置**：`apps/api/src/dcode_api/errors.py:6`（仅定义，全仓库无调用）。
- **建议修复**：删除；或若要保留统一错误层，就把各路由内联的 `HTTPException{code,message}` 收敛到一个错误工厂。
- **工作量**：S。
- **✅ 状态（2026-07-26，`7ee4ac7`）**：已删除整个 `apps/api/src/dcode_api/errors.py`（全仓无引用）。api 测试/ruff/mypy 全绿。

### P3-3 ✅ MAX_STEPS 重复且 settings 版本未被读取
- **位置**：`apps/agent/src/dcode_agent/state.py:11`（`MAX_STEPS=8`，被 graph.py:25,143 使用）vs `apps/agent/src/dcode_agent/settings.py:9`（`max_steps=8`，无人读）。
- **风险**：两处默认都是 8，一旦有人改 settings 期望生效，实际不会——静默漂移。
- **建议修复**：删掉其一。推荐让 graph 读 `agent_settings.max_steps`，删除 `state.MAX_STEPS`，使其可配置。
- **工作量**：S。
- **✅ 状态（2026-07-26，`ff02fab`）**：`graph.py` 改读 `agent_settings.max_steps`，删除 `state.MAX_STEPS` 常量——单一来源、可通过环境变量 `MAX_STEPS` 配置。agent 测试/ruff/mypy 全绿。

### P3-4 worker warnings 收集后从不持久化
- **位置**：`stages/parse.py`（填充 `ctx.warnings`）；`pipeline.py`（从不写出）。
- **问题**：因编码/语法错误被跳过的文件对用户完全不可见。
- **建议修复**：把 warnings 写入 `repos` 新列或 Redis `job:{id}` 快照，并在 `GET status` 返回，前端 Index 页展示"N 个文件被跳过"。
- **工作量**：S。

### P3-5 eval agent_base_url 未接线（对应绕缓存的直连-agent B4 路径）
- **位置**：`apps/eval/src/dcode_eval/settings.py:8`（`agent_base_url`，仅定义、全仓零读取；**不在** `SharedSettings` base，而在 `EvalSettings` 子类）；B4 的 `baselines/common.py:49` 实际 POST 到 `api_base_url` `/api/v1/query`（网关）。
- **重查结论（勿轻删）**：网关 `/api/v1/query` 会把成功结果按 `query:{repo_id}:{hash}` 缓存 1h（`routes/query.py`），命中即回放、不调用 agent。因此当前 B4 走网关**会命中查询缓存**——重跑同一套题时拿到的是缓存旧答案而非 agent 全新运行，污染可复现性（NFR）。`agent_base_url` + agent 的 `/internal/query`（eval 已有 `internal_api_key`/`internal_auth_headers`）恰好能**绕过缓存**做干净测量。git 溯源：与 `api_base_url` 同在初始提交 `37cabb5` 一次性预留，从未接线（"定义 ≠ 有用"，与已修的 P3-3 同类）。
- **建议修复**：**(A, 推荐)** 给 B4 增加"直连 agent、绕缓存"的路径（`agent_base_url` + `/internal/query` + 内部鉴权），把死开关变成服务可复现性的真功能；或 **(B)** 若接受网关缓存路径，则删除该字段并在文档写明缓存对重跑的影响。
- **工作量**：S。

### P3-6 文档 ↔ 代码漂移（含一个设计了未实现的路由）
- **位置**：`docs/en/Technical_Design.md:126-131`（内部 API 列 6 条：`search/find_definition/find_references/dependencies/dependents/file_context`）vs `apps/api/.../routes/internal.py`（实际 5 条：`search/find_definition/find_references/get_dependencies/get_file_outline`）；README 的 `chunks` 建表 SQL 缺少实际存在的 `parent_symbol/signature` 等列。
- **重查结论（不只是文档 typo）**：doc 里的 `/internal/dependents`（入向/反向依赖查询）**并非笔误**——迁移 `001` 专门建了反向边索引 `ix_edges_target (repo_id, target_id, edge_type)` 来支撑它，即它是**设计过但未实现**的功能（当前只有出向 `get_dependencies`）。
- **建议修复**：拆成两件事——(1) 命名/schema 漂移（`dependencies`↔`get_dependencies`、`file_context`↔`get_file_outline`、chunks 列）以代码为准更新文档；(2) `dependents` 作为**决策**：要么实现该反向依赖路由（索引已就绪），要么在文档中删除并注明由 `find_references` 覆盖。长期用 OpenAPI 自动导出契约。
- **工作量**：S（对齐文档）/ M（若实现 `dependents`）。

### P3-7 公开 /api/v1/* 无客户端鉴权
- **位置**：`routes/repos.py` / `routes/query.py`（无 auth 依赖）。
- **问题**：任何人可提交仓库、发起查询、消耗 embedding/agent 资源。内部路由有 `X-Dcode-Internal-Key`，但公开面无鉴权/限流。
- **建议修复**：M2 引入 API key 或 OAuth + 按租户限流；至少对 `POST /repos` 加限流防滥用（配合 SSRF 防护）。
- **工作量**：M。

### P3-8 no-op lifespan + 惰性模块单例
- **位置**：`apps/api/.../main.py:18-21`（lifespan 空转）、`deps.py`（redis/httpx/embedding/reranker 惰性单例，`TODO(M2)`）；agent 亦类似。
- **问题**：首个请求承担连接建立开销，与 NFR TTFB≤3s 相悖；连接生命周期未随 app 管理。
- **建议修复**：在 lifespan 里初始化并复用连接池（DB/Redis/httpx/RabbitMQ），关闭时清理。
- **工作量**：M。

### P3-9 worker 失败路径可逃逸"总是 ack"
- **位置**：`apps/worker/src/dcode_worker/pipeline.py`（except 分支内 `_update_repo` 若 repo 行缺失会 `RuntimeError`，`pipeline.py:217`）。
- **问题**：正常路径靠吞异常 + `message.process()` 实现"总是 ack、失败不重投"。但若 repo 行不存在（例如被删），失败处理里的持久化会再抛错并逃出 `handle_job` → 消息被 nack/重投 → 可能无限重投同一坏消息。
- **建议修复**：失败持久化也用 try/except 包裹；repo 行缺失时直接 ack 丢弃并记日志。
- **工作量**：S。
- **✅ 状态（2026-07-26，`c672f5d`）**：新增 `RepoRowMissingError`——成功路径遇它良性丢弃（repo 已删 → ack + warn）；失败持久化抽成 `_record_failure` 并用 try/except 兜底（repo 缺失或 PG 挂都只记日志不抛）。`handle_job` 对可解析消息恒不抛异常，"总是 ack / 不重投"不变量成立。新增两条逃逸路径测试。

### P3-10 前端无障碍与小瑕疵
- **位置**：`apps/frontend/src/pages/QueryPage.tsx`（流式事件区无 `aria-live`）、`src/api/client.ts:49`（过期 TODO：所述 SSE 解析其实下方已实现）、`toKnownRepoStatus` 在 IndexPage/QueryPage 重复、`finalAnswer/partialAnswer` 每次 render 反转数组未 memo。
- **建议修复**：给流式区加 `aria-live="polite"`；删除过期 TODO；抽公共 `toKnownRepoStatus`；用 `useMemo` 缓存派生态。
- **工作量**：S。

### P3-11 agent 图的 error 边不可达
- **位置**：`graph.py:149`（`decide_after_plan`）与 `graph.py:184`（`tool_call` 条件边）读 `state.error`；但**任何节点都不写** `state.error`（重查确认：全 agent 源码只有这 2 处读、0 处写），工具异常直接 bubble 到 `main.py` 转成 SSE error。
- **建议修复（推荐接线，而非删）**：让 `tool_call_node` 捕获工具异常并写入 `state.error`，使图能**在内部优雅收尾**（走到 synthesize，产出带错误说明 + 已得部分证据的答案），而不是工具一失败就把整条查询丢给 `main` 的兜底 error。删除死边是次选。
- **工作量**：S。
- **✅ 状态（2026-07-26，`c404b90`）**：`tool_call_node` 经新增的 `_record_tool_failure` 捕获工具异常（无效 args / 检索·图 API / 文件系统），写 `state.error` 并发 `error:` 的 tool_result；已有条件边据此路由到 synthesize，`synthesize_node` 前置 `⚠️` 失败提示。原先不可达的 error 边现已激活。新增降级测试；agent 测试/ruff/mypy 全绿。

### P3-12 前端类型手动镜像后端
- **位置**：`apps/frontend/src/api/types.ts:1-6`（注释：手动同步，M2 计划 OpenAPI 生成）。
- **建议修复**：从 FastAPI OpenAPI 生成 TS 类型（如 `openapi-typescript`），消除人工漂移。
- **工作量**：M。

### P3-13 缺可观测性（tracing/metrics/checkpointer）
- **位置**：`graph.py:160`（`TODO(M2)` 接 checkpointer + observability hooks）；全栈只有结构化 JSON 日志，无 metrics/trace。
- **建议修复**：LangGraph 接 checkpointer（可恢复/可观测）；加请求级 trace id 贯穿 api→agent→tools；导出关键指标（索引耗时、检索延迟、groundedness 分布）。
- **工作量**：M。

### P3-14 部署未闭环
- **位置**：README §Deployment；`docs/en/Outstanding_Work.md`。
- **问题**：`dcode.odieyang.com` 未公网解析，生产 compose 仅本地验证，外部演示验收项仍开放。
- **建议修复**：确定托管环境，配置 DNS/TLS，跑通 `prod-up`+`prod-migrate`+`prod-smoke` 的公网版本。
- **工作量**：M。

### P3-15 缺真实依赖的集成/端到端测试
- **位置**：各 `tests/` 均用注入 fake（单元覆盖良好），但无对真实 PG/pgvector/Redis/RabbitMQ 的集成测试，`test_internal_validation.py` 的 live 路径被 `DCODE_LIVE_REPO_ID` 门控默认跳过。
- **建议修复**：加一条 docker-compose 起真实依赖的集成测试流水线（可用 GitHub Actions services），至少覆盖"索引一个小仓库 → 查询 → SSE 事件齐全 → groundedness 生效"的端到端路径。
- **工作量**：M。

---

## 建议的改进路线（分阶段）

**阶段 1 — 完整性与真实基线（先让结论可信）**
- 修 P0-1（强制 groundedness）、P0-2（重跑并覆盖过期快照）。
- 打通 P1-1（真实 embedding/reranker sidecar）作为 P0-2/P1-2 的前提。
- 顺手清理 P3-1/P3-2/P3-3/P3-5/P3-6（低风险死代码与文档漂移）。

**阶段 2 — 让 H1 可被诚实检验**
- P1-2（真实 Judge + win-rate）、P1-3（扩数据集 + 统计显著性）。
- P2-1（补 inherits/references 边，强化结构感知增量）。
- P3-15（端到端集成测试兜底）。

**阶段 3 — 把 B4 做成"真·全系统"**
- P1-4（LLM 规划 + 合成）、P2-5（token 流式）。
- P3-8（连接池/lifespan）、P3-13（可观测性）。

**阶段 4 — 产品化与扩展**
- P3-7（公开鉴权/限流）、P3-14（部署闭环）、P3-12（类型代码生成）、P3-10（无障碍）。
- P2-2（多语言，启用 tree-sitter）、P2-3/P2-4（切片质量）。

---

## 参考

- 设计权威：`docs/en/Technical_Design.md`
- 现状/遗留：`docs/en/Outstanding_Work.md`、`docs/en/Final_Report.md`、`docs/en/H1_Decision.md`
- 真实模型复现：`docs/en/Sidecar_Smoke.md`
- 仓库结构：`docs/en/Repository_Structure.md`
