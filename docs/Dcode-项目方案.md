# Dcode — Codebase Onboarding Assistant 项目方案

> 项目名 **Dcode**（"Decode" 去一个 e 的造词）。寓意：帮新人"解码"一个庞大 codebase——语义层告诉你"在哪"，结构图层告诉你"谁连着谁"，Agent 带你"怎么走"。造词降低撞名概率，开工前顺手确认 GitHub 仓库名 / 域名可占即可。

---

## 0. 一句话定位

一个面向新人 onboarding 的**结构感知代码理解平台**：用户提交一个 GitHub 仓库，系统异步建立「语义索引 + 代码结构图」，然后通过一个多工具 ReAct Agent，用自然语言回答关于这个 codebase 的跨文件、架构层面的问题，并给出可跳转、可验证的代码引用。

**个人定位绑定**：这不是"又一个 RAG chatbot"。它的护城河在后端——异步索引管线、多租户、缓存、向量 + 图混合存储。Agent 只是这套平台的查询前端。对外叙事是「我设计了一套支持异步索引的代码理解平台」，正好命中 *Agent/LLM 应用 × 后端基础设施* 的核心定位。

---

## 1. 核心论点（整个项目和 eval 都围绕它）

> **传统关键字搜索（GitHub Search）和扁平向量 RAG，本质都解决"相似度"问题；而新人最想知道的"调用逻辑、架构层次、上下文依赖"，本质是"结构关系（graph）"问题。**
>
> 因此：**结构感知索引 + Agent 多步工具调用**，在需要跨文件推理的代码理解任务上，显著优于扁平向量 RAG 和关键字搜索。

这条假设是可证伪的，后面 eval 的全部目的就是量化验证它——尤其是在"跨文件/架构型"问题上拉开差距。

---

## 2. 范围（务必收窄，否则做不完）

**In scope**
- 单语言：**Python**（tree-sitter / jedi / 生态最成熟）
- 1–3 个中等规模、知名开源 repo 作为索引与评测对象（建议：`requests`、`flask`、`fastapi` 任选）
- 异步索引管线、混合检索、代码结构图、ReAct Agent、完整 eval、简洁 Web UI

**Out of scope（stretch goal，砍了不心疼）**
- 多语言支持
- 解析任意配置文件 / 构建系统（价值低，优先级靠后）
- 代码图可视化大屏（能做就锦上添花，做不完不影响论点）
- 实时增量索引（首版全量重建即可）

**目标 repo 选择标准**：纯 Python、依赖关系清晰、有真实 issue/PR 可挖作为 ground truth、规模在数千~数万行（不要选 Django 这种巨无霸首版）。

---

## 3. 系统架构（七个组件 + 数据流）

```
[用户提交 repo URL]
        │
        ▼
 ┌─────────────────┐   入队    ┌──────────────────────────────┐
 │  API / Gateway  │ ───────▶ │   Index Queue (消息驱动)        │
 │ (多租户/鉴权)    │          └──────────────┬───────────────┘
 └────────┬────────┘                         │ 拉取任务
          │ 查询状态/提问                       ▼
          │                      ┌────────────────────────────┐
          │                      │      Index Worker          │
          │                      │ clone → AST 切块 → metadata │
          │                      │ → embedding(批量/重试/缓存) │
          │                      │ → jedi 建 def/ref 调用图     │
          │                      └──────────────┬─────────────┘
          │                                     ▼
          │                      ┌────────────────────────────┐
          │                      │  PostgreSQL + pgvector      │
          │                      │  - chunks + 向量            │
          │                      │  - code graph (符号/边)      │
          │                      │  Redis: embedding/查询缓存   │
          │                      └──────────────┬─────────────┘
          ▼                                     │
 ┌─────────────────────────────────────────────┴──────────────┐
 │                  Retrieval & Structure Layer                │
 │  hybrid retrieval (dense+BM25)+rerank | code graph 查询 API  │
 └────────────────────────┬────────────────────────────────────┘
                          │  封装成 tools
                          ▼
 ┌────────────────────────────────────────────────────────────┐
 │                  Agent (ReAct / LangGraph)                   │
 │  search_code / read_file / find_definition / find_references │
 │  / get_dependencies / get_file_outline / grep ...            │
 │  + groundedness 校验 + SSE 流式输出                            │
 └────────────────────────┬────────────────────────────────────┘
                          ▼
                  [Web UI: 聊天 + 引用跳转 + 索引状态]

 ┌────────────────────────────────────────────────────────────┐
 │  Eval Harness（离线）: 问题集 + baseline 阶梯 + 指标 + 分析    │
 └────────────────────────────────────────────────────────────┘
```

---

## 4. 模块规格（这就是后面的工作流 A–F）

### A. 索引管线 Ingestion & Indexing（后端核心 / 差异点）
- **职责**：repo clone → tree-sitter **AST 级切块**（按函数/方法/类边界，不要定长滑窗）→ 抽取结构化 metadata（文件路径、语言、所属类、函数签名、import 列表）→ 批量 embedding（含速率限制处理、失败重试、`Redis` 缓存去重）→ 写入 `pgvector` → 用 **jedi** 抽 def/reference 关系建代码图。
- **关键设计**：必须**异步**。提交即入队，worker 消费，前端轮询状态（`queued → cloning → parsing → embedding → graphing → ready`）。这套消息驱动 + 状态机可平移 Nexus 的经验。
- **技术**：tree-sitter（切块）、jedi/LSP（结构）、消息队列（RabbitMQ 或轻量方案）、PostgreSQL + pgvector、Redis。
- **接口**：`POST /repos`（提交索引）、`GET /repos/{id}/status`、内部 worker 消费协议。

### B. 检索与结构层 Retrieval & Structure
- **职责**：把"找代码"做对。
    - 语义层：**hybrid retrieval** = dense（pgvector embedding）+ sparse（BM25）双路召回 + reranker（bge-reranker / Cohere rerank）。
    - 结构层：基于代码图的查询 API——`find_definition`、`find_references`、`get_dependencies`、`get_file_outline`。
- **为什么 hybrid**：代码里 symbol 精确匹配极重要（搜 `validate_token` 要确切符号），但自然语言问题又需要语义。GitHub Search 本质是 sparse-only，所以用 hybrid 才算公平且有看点地超越它。
- **接口**：`search(query, k)` → ranked chunks；图查询 API（供 C 封装成 tools）。

### C. Agent 编排 Agent Orchestration
- **职责**：ReAct 循环（LangGraph 状态机），由 Agent 自行判断一个问题需要语义搜索、结构遍历还是两者交替迭代。
- **Tools 清单**：
    - `search_code(query)` — 混合检索入口（语义）
    - `read_file(path, line_range)` — 读确切代码
    - `find_definition(symbol)` / `find_references(symbol)` — 跳转定义 / 谁在调用（来自代码图）
    - `get_dependencies(module)` — import / 依赖图
    - `get_file_outline(path)` — 文件里有哪些类和函数
    - `grep(pattern)` — 精确符号搜索，便宜又准
    - `list_directory` / `get_repo_tree` — 导航
- **多跳样例**："鉴权怎么做的" → `search_code` 找到 auth 模块 → `read_file` → `find_references` 看谁在用 → 综合答案 + 引用。这个**跨文件多跳编排**就是相对裸 RAG 的核心差异。
- **硬约束**：答案里的每个符号/路径引用，必须经 **groundedness 校验**（见 D）——代码场景编造一个不存在的函数是致命的。
- **技术**：LangGraph、SSE 流式（复用 ETHIS 的 FastAPI SSE 经验）。

### D. 评估 Eval Harness（你的主场 / 课程最看重）
- **问题集构造**（早动手，规模小而精，~50–80 题）：
    1. 手标：20–50 个问题对应的相关文件/chunk（ground truth）。
    2. 合成：拿一个函数让 LLM 生成"它能回答的问题"，ground truth 即该函数，可规模化。
    3. 真实信号挖掘：GitHub issue 引用的文件、commit message 对应的改动文件。
- **问题分类（taxonomy，强烈建议）**：单文件事实型 / 跨文件结构型 / 架构理解型，分别看赢多少——结论大概率是"单文件大家都行，跨文件和架构型完整系统碾压"，正好印证核心论点，可解释性强。
- **Retrieval 指标**：Recall@k、MRR、nDCG、Hit@k。
- **Agent 答案评估（三层叠加）**：
    1. LLM-as-judge 按 rubric 打分（correctness / completeness / faithfulness / actionability）；
    2. **pairwise win-rate**（本系统 vs 裸 RAG，judge 二选一），比绝对分更可靠；
    3. **programmatic groundedness check**：答案引用的符号/路径是否真在 repo 里存在——不靠 LLM、直接代码校验，既是幻觉率指标又是 guardrail。
- **Baseline 阶梯（递进，避免稻草人）**：
  `GitHub Search（纯关键字）` → `BM25` → `vanilla dense RAG` → `hybrid RAG` → `hybrid + 结构图（完整系统）`。每加一层涨多少，一目了然。
- **可选 ablation**：通用 embedding（text-embedding-3）vs 代码专用 embedding（voyage-code / jina-code）。
- 复用 Verdict / &Open 的 LLM-as-Judge 经验。

### E. 前端 / 聊天 UI Frontend
- **职责**：聊天界面 + repo 选择/提交 + **索引状态实时展示**（轮询/SSE）+ 引用渲染（点击跳转到对应代码行）。
- **加分项（stretch）**：代码图的小型可视化（你做过 Raft visualizer 的 React/WebSocket，有底子）。
- **审美**：沿用 odieyang.com 的 Morandi / glassmorphism 风格，保持作品集视觉一致性。
- 原则：简洁能用即可，**别陷进去**。

### F. 基础设施 / 部署 / 粘合 Infra & Glue（横切）
- 多租户隔离（多 repo / 多用户，平移 Tollgate 的多租户 + ACID 思路）。
- Redis 缓存（embedding 缓存、热点符号查询缓存、查询去重）。
- API gateway / 鉴权、Docker 化、部署到 `dcode.odieyang.com` 子域。
- README + 技术博客 + 架构图。

---

## 5. 分工（三人）

核心原则：**你（Odie）坐在 A 索引管线 + C Agent 这条最高价值的脊柱上，并兼任总架构/集成 owner**——这俩是和 *Agent × 后端基础设施* 定位绑死、面试会往死里问的部分，不能让出去。两端都是你的，所有模块间接口也由你拍板。

### 你（Odie）— 索引管线 A + Agent C + 架构/集成
- 第1周：heads-down 打通 A（AST 切块 → 异步 worker → embedding → pgvector → jedi 建图），并与 P2 共定表结构/接口。
- 第2–3周：在 P2 的检索 API 之上搭 C（ReAct + tools + SSE + groundedness 校验）。
- 第4周：与 P2 一起集成、部署上线。
- 备注：A 在前、C 在后，时间错开，是顺序不是并发；作为 lead + 旗舰项目，负载合理。

### P2 — 检索与结构层 B + 存储/基建 F
后端中段 + serving，独立把"给个 query 返回 ranked chunks / 图答案"做干净，并扛起存储与部署这层基建。
- 第1周：搭 pgvector / BM25 / Redis 基建，**与你一起共设计 chunk 表和代码图的点边结构**（全项目最关键的同步点）。
- 第2周：hybrid retrieval + rerank + 代码图查询 API（你的 tools 即来自这里）。
- 第3–4周：多租户、缓存调优、Docker、部署子域。

### P3 — 评估 D + 前端 E
证明 + 门面，全项目**最可并行**的部分——D 第1周就能独立动起来，不必等 A/B/C，全程不闲。
- 第1周：构造问题集（手标 + 合成 + 挖 GitHub issue）+ 搭 eval 脚手架（完全独立）。
- 第2周：对着 mock agent 接口先把 UI 壳搭出来。
- 第3周（eval 大周）：跑完整 baseline 阶梯 + taxonomy 分类分析 + judge + groundedness check，同时完成 UI。
- 第4周：UI 打磨 + 出最终结果图表。

### 三个必须钉死的接口契约（分工能否跑通全看这三处）
1. **A↔B：DB schema**（你 + P2，第1周必须共定）—— chunk 表、向量列、代码图的点和边怎么存。两个后端人本就该结对。
2. **B→C：检索 API 契约** —— `search(query,k)` 与图查询返回什么结构；你是消费方，必须你拍板，别让 P2 自定后你迁就。
3. **C→E / C→D：Agent 的 SSE 输出 + 引用格式** —— P3 的 UI 和 eval 都靠它，早冻结。

### 负载与微调
- 负载：你最重、P3 次之、P2 略轻——这是对的，但 P2 第1周务必被基建活填满，别让他等你的 A。
- 这是**按模块逻辑**给的默认分配。你比我清楚队友强项：若有人前端强，E 从 P3 拆一点给他；若 P2 是 infra 型，F 多压给他、B 分一点回中间。按真实强项微调即可。
- 课程 rubric 想要的（RAG 基本功 + eval）是本系统的干净子集，交课时挑 A 简化版 + B + C 基础版 + D 打包即可。**记得对照实际 rubric 核一遍**——本节未对任何具体评分项做假设。

---

## 6. 时间线（今天 6/9，提前批 7 月开，有效窗口 3–4 周，与 LeetCode/八股/两门课并行）

**MVP 优先，每周一个能跑通的纵向切片：**

- **第 1 周｜索引管线打通**：AST 切块 + 异步 worker + pgvector 落库。目标：**一个 repo 端到端进库**（检索粗糙没关系）。
- **第 2 周｜检索 + Agent**：hybrid + rerank + jedi 结构工具 + 基础 ReAct 循环。目标：**单 repo 能问能答**。
- **第 3 周｜Eval + UI**：eval harness + baseline 阶梯 + 简洁 UI。你的主场，**别压缩**。
- **第 4 周｜上线 + 收尾**：部署子域、跑全部结果、写 README/技术博客、留 buffer。

**若时间被压缩，按此优先级保命：**
异步索引管线（后端故事）→ 结构感知检索打赢 baseline（核心论点）→ 小而干净的 eval（证明论点）→ UI 够用。配置文件解析、多语言、图可视化全部砍。

---

## 7. 成本与选型注意

- **Embedding 走本地自托管模型**（jina-code / bge-code 类）：索引一个真实 repo 是几千次调用，本地省钱、不卡速率，还多一个"我自己部署了 embedding 服务"的 infra 亮点。生成与 judge 再走 API。
- 向量与代码图都压进 **PostgreSQL + pgvector**：省一个独立向量服务，且更能体现数据库深度，比"再起一个 Qdrant"更贴你的定位。
- 具体哪个代码 embedding 模型当前效果最好、显存要求多少——这块更新很快，开工前实测一轮再定。

---

## 8. 面试话术钩子（项目做完后的回报）

每个钩子都对应面试官会深挖、且是你主场的方向：

- "为什么索引必须异步？"→ 几千次有速率限制的 embedding 调用 + 解析 + 建图，同步必然超时；讲队列、worker、状态机、重试。
- "向量数据库怎么选的？"→ pgvector vs 独立向量库的权衡，多租户隔离，缓存策略。
- "你的 Agent 凭什么比裸 RAG 强？"→ 结构图 + 多跳工具编排，附 eval 里跨文件/架构型问题的 win-rate 数据。
- "怎么防代码幻觉？"→ programmatic groundedness 校验，把符号/路径回查 repo。
- "怎么证明它真的有用？"→ 递进 baseline 阶梯 + 问题 taxonomy 分类分析。

---

*这份方案是后续所有开发的锚点。下一步建议先定第 1 周索引管线的接口与表结构，或把本架构画成正式系统图。*