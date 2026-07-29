# Dcode 问题清单与改进路线（Problem Register）

> ## 📁 已归档 — 开发期记录，非当前状态
>
> 这是开发过程中用的代码级问题登记表，**内容停在 2026-07-27**，此后发生的事（前端整体重写、真实模型 H1 运行、评估数字改为机械生成）都不在里面。其中若干条已经完成但未划掉，例如 P0-2（评估快照早于代码）和 P1-1（全 stub 模型导致 B2=B3=B4）都已解决。
>
> **当前状态请看**：[`docs/en/Final_Report.md`](../en/Final_Report.md)（H1 结论、重开条件、剩余工作）、[`CLAUDE.md`](../../CLAUDE.md)（面向 agent 会话的操作状态）。
>
> 保留原因：P0–P3 的分级与诊断过程本身有参考价值，而删掉一份真实的历史记录不是这个项目的做法。

> 目的：把当前实现与 Dcode 设计目标（尤其是 **H1 假设**）之间的差距，整理成一份可执行、可拆成 issue/PR 的问题登记表，用于全面提升项目质量。
>
> 生成日期：2026-07-26 ｜ 依据：对全仓库（`packages/shared` + 6 个服务 + 前端 + infra + docs）的通读。
> 标 ✅ 的问题已直接在源码中核实过（非推断）。
>
> **更新 2026-07-26**（同步 `origin/main`@`4710602`，PR #10）：已并入「加权 RRF 融合」——混合检索由 1:1 等权改为 **dense:sparse = 2:1**（`RRF_DENSE_WEIGHT`/`RRF_SPARSE_WEIGHT`，tie-break 改 dense 优先；见 `apps/api/src/dcode_api/routes/internal.py` `_fuse_search_candidates`）。该改动**只在真实 embedding 下生效**（stub 下 dense 返回空、权重为零），不改变下列任何问题的成立性。
>
> **拆分 2026-07-26**：已完成项（划线）的实现细节移至 [`Improvement_Log.md`](Improvement_Log.md)；本文件保留全量概览表 + **仅未完成项**的详情 + 改进路线。
>
> **更新 2026-07-27**：LLM 合成线落地——**P2-5**（token 流式）✅、**P1-4 的合成部分**✅（可选 OpenAI，带引用 + 逐 token 流式 + 引用白名单 grounded 1.0）；P1-4 仅剩 **LLM 规划**未做。真实 sidecar（Jina 768 + BGE）端到端跑通并记入 [`Sidecar_Smoke.md`](../en/Sidecar_Smoke.md)（P1-1 路径已验证，但完整评测刷新 P0-2 仍未做）。详见 [`Improvement_Log.md`](Improvement_Log.md)。

## 如何阅读

- **优先级**：`P0`(完整性/误导，最高) → `P1`(H1 可信度，项目核心使命) → `P2`(能力缺口) → `P3`(技术债/漂移/健壮性/无障碍/运维)。
- **类型**：`缺陷`=行为错误或误导；`缺口`=已规划但未实现（多为 M2/M3）；`债务`=可运行但不干净/易漂移。
- **工作量**：`S`≈半天内 ｜ `M`≈1–3 天 ｜ `L`≈>3 天或需先设计。

---

## 概览表

> 划线 + ✅**已修复** = 已完成，实现细节见 [`Improvement_Log.md`](Improvement_Log.md)；下方详情仅列**未完成**项。

| ID | 优先级 | 类型 | 领域 | 一句话 | 工作量 |
|---|---|---|---|---|---|
| ~~P0-1~~ | P0 | 缺陷 | Agent/Groundedness | ✅**已修复**：groundedness 现强制剥离未验证引用 + 仅透出已验证引用 + 阈值可配 | M |
| P0-2 | P0 | 缺陷 | Eval | 已提交的 `results/eval-suite/` 快照早于当前代码，误导性 ✅ | S |
| P1-1 | P1 | 缺口 | Eval/模型 | 默认全 stub 模型 → H1 无法真实测量，B2=B3=B4 指标相同 | M |
| P1-2 | P1 | 缺口 | Eval/Judge | LLM-as-Judge 是 stub → pairwise win-rate 恒为 None | M |
| P1-3 | P1 | 缺口 | Eval/数据集 | 仅 16 题、单一仓库、无统计显著性（固定 0.05 阈值启发式） | L |
| P1-4 | P1 | 缺口 | Agent | 合成已接 LLM（可选 OpenAI，带引用+流式+白名单 grounded 1.0）✅；**规划仍关键词路由** | M |
| ~~P2-1~~ | P2 | 缺口 | Worker/Graph | ✅**已修复**（`67fb694`）：产出 inherits + references 边（references 经 find_references 透出） | M |
| P2-2 | P2 | 缺口 | Worker | 仅索引 Python | L |
| ~~P2-3~~ | P2 | 缺陷 | Worker/Chunk | ✅**已修复**（`a2318bf`）：改用 `ast.unparse` 重建完整签名 | S |
| ~~P2-4~~ | P2 | 缺陷 | Worker | ✅**已修复**（`565233d`）：max_file_bytes(1MB) 跳过 + max_chunk_chars(20k) 截断 | S |
| ~~P2-5~~ | P2 | 缺口 | Agent/SSE | ✅**已修复**：LLM 合成逐 token 流式 + 前端累加 delta | M |
| ~~P3-1~~ | P3 | 债务 | Worker/依赖 | ✅**已修复**（`2a45c4a`）：删除死依赖 + 重新锁定 | S |
| ~~P3-2~~ | P3 | 债务 | API | ✅**已修复**（`7ee4ac7`）：删除死代码 `errors.py` | S |
| ~~P3-3~~ | P3 | 债务 | Agent/配置 | ✅**已修复**（`ff02fab`）：去重，改为读 `AgentSettings.max_steps` | S |
| ~~P3-4~~ | P3 | 缺陷 | Worker | ✅**已修复**（`267fa74`/`bb7d8bf`）：warnings 写入 job 快照 + status 透出 + 前端展示 | S |
| ~~P3-5~~ | P3 | 缺口 | Eval/可复现性 | ✅**已修复**（`63c32e5`）：B4 直连 agent `/internal/query`，绕过查询缓存 | S |
| ~~P3-6~~ | P3 | 债务/缺口 | 文档漂移 | ✅**已修复**（`cb204d0`/`7a92493`）：实现 `dependents` 全链路 + 文档对齐 | M |
| P3-7 | P3 | 缺口 | API/安全 | 公开 `/api/v1/*` 无客户端鉴权（M2） | M |
| ~~P3-8~~ | P3 | 债务 | API | ✅**已修复**（`3427f16`）：lifespan 拥有 Redis + agent 客户端生命周期（启动 warm / 关闭 close） | M |
| ~~P3-9~~ | P3 | 缺陷 | Worker | ✅**已修复**（`c672f5d`）：`RepoRowMissingError` 良性丢弃 + 失败持久化兜底，`handle_job` 恒不抛 | S |
| ~~P3-10~~ | P3 | 缺陷 | Frontend/无障碍 | ✅**已修复**（`09e2446`）：aria-live + 抽共享 util + useMemo + 清 TODO | S |
| ~~P3-11~~ | P3 | 债务 | Agent | ✅**已修复**（`c404b90`）：工具失败写 `state.error`，图内优雅降级 | S |
| P3-12 | P3 | 债务 | Frontend | 类型手动镜像后端 schema → 应改 OpenAPI 代码生成（M2） | M |
| P3-13 | P3 | 缺口 | 可观测性 | 无 tracing/metrics；LangGraph 无 checkpointer（graph.py:160 TODO） | M |
| P3-14 | P3 | 缺口 | 运维/部署 | `dcode.odieyang.com` 未解析；生产 compose 仅本地验证 | M |
| P3-15 | P3 | 缺口 | 测试 | 全部靠注入 fake，无真实 PG/Redis/RabbitMQ 的集成/端到端测试 | M |
| ~~P3-16~~ | P3 | 缺陷 | 前端/测试 | ✅**已修复**（`a311e16`）：Node 26 原生 localStorage 破坏 jsdom → vitest 全挂 | S |

> 已修复 16 项、未完成 11 项（P1-4 合成部分已完成，仅剩 LLM 规划）。下方详情仅列未完成项。

---

## P0 — 完整性问题（正在误导使用者/评审者）

### P0-2 ✅ 已提交的评测快照早于当前代码，具误导性
- **位置**：`results/eval-suite/{B2,B3,B4}/`、`results/eval-suite/{suite_summary,h1_report}.json`。
- **问题**：各 baseline 子目录**只有** `metrics.json / per_question.jsonl / taxonomy_breakdown.json`，**缺 `run_config.json`**——而当前 `run.py:44` 每次运行都会写 `run_config.json`（`test_run.py` 也断言了）。快照日期为 6 月 16 日，B4 答案文本（"Top code hits for…"、引用测试文件）既不符合当前 `template_answer` 也不符合 SSE 路径。README 直接引用了这些数字作为"当前 H1 结论"。
- **影响**：README/`Final_Report.md`/前端 Compare 页展示的都是过期结果；任何人据此判断 H1 都是基于失效数据。
- **建议修复**：在真实 sidecar（Jina 768 + BGE reranker）下重新索引目标仓库并重跑 `run_suite`，覆盖 `results/eval-suite/`，同步更新 README §Current Result、`Final_Report.md`（含 H1 结论）和前端 `evalSnapshot.ts`。在结果目录补 `run_config.json`（记录模型配置 + commit + 问题集）。
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

### P1-4 Agent 规划仍规则驱动（合成已升级为 LLM）
- **位置**：`apps/agent/src/dcode_agent/graph.py`（`_select_initial_tool` 关键词路由——**规划部分**）。
- **进展（2026-07-27，合成已完成）**：新增可选 OpenAI 合成层（`SYNTHESIS_MODEL`/`OPENAI_API_KEY`，默认 stub）——基于检索证据流式生成带引用的人话答案、逐 token 流式（P2-5）、并用"引用白名单"把 groundedness 稳在 **1.0**；模板保留为降级路径；groundedness 护栏不变。详见 [`Improvement_Log.md`](Improvement_Log.md)（`62b8a49`/`f613265`/`859d8cc`）。
- **仍未完成（本项剩余）**：**LLM 规划**——工具选择/参数仍是子串关键词路由（`_select_initial_tool`），未交给 LLM。
- **影响**：合成侧"实现-目标落差"已消除（B4 答案是真推理生成 + 可核实引用）；规划侧仍规则驱动。
- **建议修复**：把工具选择/参数交给 LLM（保留规则路径为降级），完成"真·全系统"最后一块。
- **工作量**：M（仅剩规划）。

---

## P2 — 能力缺口

### P2-2 仅索引 Python
- **位置**：`stages/parse.py`（只 `rglob *.py` + stdlib `ast`）。
- **问题**：非 Python 仓库无法索引。README/文档也已声明此边界。
- **建议修复**：中长期引入语言无关解析（此处 `tree-sitter` 依赖终于有了用武之地——注：已在 P3-1 删除，实现多语言时按需加回），先支持 JS/TS。
- **工作量**：L。

---

## P3 — 技术债 / 文档漂移 / 健壮性 / 无障碍 / 运维

### P3-7 公开 /api/v1/* 无客户端鉴权
- **位置**：`routes/repos.py` / `routes/query.py`（无 auth 依赖）。
- **问题**：任何人可提交仓库、发起查询、消耗 embedding/agent 资源。内部路由有 `X-Dcode-Internal-Key`，但公开面无鉴权/限流。
- **建议修复**：M2 引入 API key 或 OAuth + 按租户限流；至少对 `POST /repos` 加限流防滥用（配合 SSRF 防护）。
- **工作量**：M。

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

（✅ = 已完成，见 [`Improvement_Log.md`](Improvement_Log.md)）

**阶段 1 — 完整性与真实基线（先让结论可信）**
- ✅ P0-1（强制 groundedness）；P0-2（重跑并覆盖过期快照，待真实模型）。
- P1-1（真实 embedding/reranker sidecar）作为 P0-2/P1-2 的前提。
- ✅ P3-1/P3-2/P3-3/P3-5/P3-6（低风险死代码与文档漂移清理）。

**阶段 2 — 让 H1 可被诚实检验**
- P1-2（真实 Judge + win-rate）、P1-3（扩数据集 + 统计显著性）。
- ✅ P2-1（补 inherits/references 边，强化结构感知增量）。
- P3-15（端到端集成测试兜底）。

**阶段 3 — 把 B4 做成"真·全系统"**
- ✅ P2-5（token 流式）；✅ P1-4 合成（LLM 合成 + 流式 + 白名单 grounded 1.0）；P1-4 规划（LLM 工具选择）待做。
- ✅ P3-8（连接池/lifespan）；P3-13（可观测性）。

**阶段 4 — 产品化与扩展**
- P3-7（公开鉴权/限流）、P3-14（部署闭环）、P3-12（类型代码生成）；✅ P3-10（无障碍）。
- P2-2（多语言）；✅ P2-3/P2-4（切片质量）。

---

## 参考

- 已完成项记录：[`Improvement_Log.md`](Improvement_Log.md)
- 设计权威：`docs/en/Technical_Design.md`
- 现状/遗留：`docs/en/Outstanding_Work.md`、`docs/en/Final_Report.md`（含 H1 结论）
- 真实模型复现：`docs/en/Sidecar_Smoke.md`
- 仓库结构：`docs/en/Repository_Structure.md`
