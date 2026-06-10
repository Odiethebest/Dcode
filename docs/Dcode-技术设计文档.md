# Dcode — 技术设计文档 (Technical Design Document)

| | |
|---|---|
| **文档类型** | Technical Design Document (TDD) |
| **版本** | v1.0 |
| **状态** | Approved for Execution |
| **关联文档** | 《Dcode 项目愿景与目标定义》（以下简称 Vision Doc） |
| **范围** | 定义本项目的系统架构、组件设计、数据模型、接口契约、团队分工与执行计划 |
| **不涉及** | 项目动机、可证伪假设、验收标准（参见 Vision Doc） |

---

## 1. 引言

### 1.1 文档目的

本文档为 Dcode 项目的实现层规约，定义系统的架构边界、组件接口、数据模型与执行计划。本文档与 Vision Doc 配套使用：Vision Doc 回答"做什么 / 为何做 / 何时算完"，本文档回答"如何实现 / 谁负责 / 何时交付"。

### 1.2 文档约定

- 凡涉及目标、范围、验收的判断，以 Vision Doc 为准；
- 凡涉及接口、模式、技术选型的判断，以本文档为准；
- 接口与数据模型的具体字段命名以本文档为约束，实现层不得擅自变更。

### 1.3 阅读路径建议

- 项目执行者：第 2、3、4、5、8、9 节
- 集成方与评测方：第 5、6 节（接口与非功能性需求）
- 课程评审：第 2、3、7、9 节

---

## 2. 系统概览

### 2.1 系统定位

Dcode 是一个**结构感知的代码理解平台**。系统接收一个 Git 仓库地址作为输入，异步建立"语义向量索引 + 代码调用图"双重索引；用户通过自然语言查询，由多工具 ReAct Agent 在两类索引上执行多步推理，返回经程序化校验的、可跳转的代码引用与答案。

### 2.2 高层架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Client / UI                                │
│                  (聊天界面 / 索引状态 / 引用跳转)                          │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTPS / SSE
┌─────────────────────────────────▼──────────────────────────────────────┐
│                      API Gateway (FastAPI)                              │
│            鉴权 / 多租户路由 / 速率限制 / 请求审计                          │
└──────┬─────────────────────────────────────────────────┬───────────────┘
       │ POST /repos                                     │ POST /query
       │ GET  /repos/{id}/status                         │ (SSE)
       │                                                 │
┌──────▼─────────────────┐                  ┌────────────▼──────────────┐
│   Index Job Queue      │                  │   Agent Orchestrator      │
│   (RabbitMQ / Redis)   │                  │   (LangGraph ReAct)        │
└──────┬─────────────────┘                  └────────────┬──────────────┘
       │                                                 │ tool calls
┌──────▼─────────────────┐                  ┌────────────▼──────────────┐
│   Index Worker(s)      │                  │   Retrieval & Graph API   │
│  clone → AST 切块       │                  │  hybrid search / graph    │
│  → 元数据 → embedding   │                  │  query / file read        │
│  → jedi 建图 → 落库      │                  └────────────┬──────────────┘
└──────┬─────────────────┘                               │
       │ 写入                                            │ 读取
       │                                                 │
┌──────▼─────────────────────────────────────────────────▼──────────────┐
│                  Storage Layer                                          │
│  PostgreSQL + pgvector  (chunks / embeddings / graph nodes / edges)     │
│  Redis                  (embedding cache / query cache / job status)    │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  Evaluation Harness (离线)                                              │
│  问题集 / Baseline 阶梯 / 指标计算 / LLM-as-Judge / Groundedness 校验    │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.3 关键设计原则

1. **索引与查询路径解耦**：索引为异步管线，查询为同步 / 流式路径；二者通过存储层异步通信。
2. **结构与语义双索引并存**：向量索引解决"在哪"，代码图解决"谁连着谁"；二者通过统一 chunk / symbol ID 关联。
3. **答案级可验证性**：所有 Agent 答案中的代码引用必须经程序化校验，作为系统级 guardrail（实现细节见 3.3.4）。
4. **存储集中化**：向量与代码图统一落 PostgreSQL，避免引入独立向量服务，简化部署与一致性管理。

---

## 3. 组件设计

### 3.1 索引管线 (Ingestion & Indexing)

**职责**：将 Git 仓库转换为可检索的结构化数据。

**处理阶段**：

| 阶段 | 输入 | 输出 | 关键技术 |
|---|---|---|---|
| Clone | Repo URL | 本地工作目录 | `git clone --depth=1` |
| Parse | 源文件 | AST 节点 | tree-sitter (Python grammar) |
| Chunk | AST | Chunk 记录（含元数据） | AST 级切块（函数 / 方法 / 类 / 模块级 docstring） |
| Embed | Chunk 文本 | 向量 | 自托管代码 embedding 模型（详见 §7） |
| Graph | AST + 符号 | 图节点 / 边 | jedi（定义、引用、依赖解析） |
| Persist | Chunk + 向量 + 图 | DB 落库 | PostgreSQL + pgvector |

**设计决策**：

- **D-3.1.1 必须采用 AST 级切块，禁用定长滑窗。** 定长滑窗会破坏函数边界、丢失 import 上下文，导致检索结果脱离调用语境后失效。
- **D-3.1.2 索引执行必须异步。** 单仓库索引涉及数千次 embedding 调用，存在速率限制与失败重试需求，同步执行不可行。
- **D-3.1.3 Embedding 调用必须经 Redis 内容寻址缓存。** 缓存键为 `embed:{model_id}:{sha256(text)}`，确保跨仓库的相同代码片段不重复计算。
- **D-3.1.4 索引状态机为单调推进**：`queued → cloning → parsing → embedding → graphing → ready`，任一阶段失败转入 `failed` 并保留错误上下文。

**对外接口**：见 §5.1。

### 3.2 检索与结构层 (Retrieval & Graph API)

**职责**：在 §3.1 落库的数据之上，提供两类查询能力：(a) 语义检索；(b) 代码图查询。

**3.2.1 语义检索（Hybrid Retrieval）**

```
query → [dense 召回 (pgvector)] ─┐
                                 ├→ Reciprocal Rank Fusion → Reranker → top-k
query → [sparse 召回 (BM25)]    ─┘
```

- **dense 召回**：query embedding 经 pgvector 余弦相似度查询；
- **sparse 召回**：BM25 索引（PostgreSQL `tsvector` 或独立 BM25 实现）；
- **融合**：Reciprocal Rank Fusion (RRF)，常数 k=60；
- **重排**：cross-encoder reranker（候选模型见 §7）。

**设计决策**：

- **D-3.2.1 dense 与 sparse 必须并行召回。** 代码场景下精确符号匹配（"找 `validate_token`"）与语义匹配（"找鉴权相关代码"）的需求并存，单路检索任一种都会失败。
- **D-3.2.2 召回 k 与最终 top-k 解耦。** 召回阶段取 top-50，重排后返回 top-10；该解耦允许重排阶段补救召回阶段的排序偏差。

**3.2.2 代码图查询**

代码图查询为只读、确定性查询，按符号或文件路径直接索引。提供以下原子操作：

- `find_definition(symbol)` — 符号定义位置
- `find_references(symbol)` — 符号引用位置（反向边）
- `get_dependencies(module)` — 模块 import 依赖
- `get_file_outline(path)` — 文件内符号列表

**对外接口**：见 §5.2。

### 3.3 Agent 编排层 (Agent Orchestrator)

**职责**：将自然语言查询转换为一系列检索 / 图查询 / 文件读取动作，并合成最终答案。

**3.3.1 架构选型**

- **框架**：LangGraph（状态机 + ReAct 循环）；
- **执行模式**：流式（SSE），中间步骤实时下发；
- **最大步数**：单次查询上限 8 步（防止无限循环），超过即强制合成。

**3.3.2 工具清单**

| 工具名 | 入参 | 输出 | 底层依赖 |
|---|---|---|---|
| `search_code` | `query: str, k: int` | `List[Chunk]` | §3.2.1 |
| `read_file` | `path: str, line_range: [int,int]` | 代码片段 | §3.1 落库 |
| `find_definition` | `symbol: str` | `List[Location]` | §3.2.2 |
| `find_references` | `symbol: str` | `List[Location]` | §3.2.2 |
| `get_dependencies` | `module: str` | `List[Module]` | §3.2.2 |
| `get_file_outline` | `path: str` | `List[Symbol]` | §3.2.2 |
| `grep` | `pattern: str` | `List[Location]` | ripgrep |
| `list_directory` | `path: str` | `List[FileEntry]` | 文件系统 |

**3.3.3 状态机定义**

```
[start] → plan → tool_call → tool_result → [decide]
                                              ├─ 继续 → plan
                                              └─ 结束 → synthesize → groundedness_check → [end]
```

**3.3.4 Groundedness 校验（Guardrail）**

合成阶段产出的答案在返回前必须通过校验：

1. 抽取答案中所有形如 `path/to/file.py:42` 与 ``` `module.Class.method` ``` 的引用；
2. 对每个引用，在 §3.1 落库的数据中查询其是否存在；
3. 不存在的引用被标记或剥离；
4. 校验结果以指标形式记录（用于 §3.4 评测）。

**设计决策**：

- **D-3.3.1 Groundedness 校验为强制硬约束，不可禁用。** 代码场景下编造不存在的符号是项目致命缺陷；该校验同时承担 Vision Doc 验收标准（≥95%）的实现路径。
- **D-3.3.2 工具调用结果必须缓存。** 缓存键为 `tool:{tool_name}:{repo_id}:{hash(args)}`，TTL 24h；显著降低重复查询成本。

**对外接口**：见 §5.3。

### 3.4 评测子系统 (Evaluation Harness)

**职责**：离线执行 Vision Doc §6 定义的全部验收指标。

**3.4.1 问题集构造**

| 来源 | 规模目标 | Ground Truth 形态 |
|---|---|---|
| 人工标注 | 20–50 | 问题 ↔ 相关 chunk / 文件集合 |
| 函数反向合成 | 30–50 | LLM 基于函数生成问题，函数本身即 GT |
| GitHub Issue / Commit 挖掘 | 视可获取量 | Issue 引用的文件即 GT |

**3.4.2 问题分类（Taxonomy）**

每题打标为以下三类之一，支持分层分析：

- **L1 单文件事实型**：答案位于单一文件内（如 "X 函数的参数有哪些"）；
- **L2 跨文件结构型**：答案需追溯调用 / 引用关系（如 "谁在调用 X"）；
- **L3 架构理解型**：答案需综合多模块（如 "鉴权流程如何实现"）。

H1 假设的关键检验落在 L2、L3 子集上。

**3.4.3 Baseline 阶梯**

| 编号 | 系统 | 含义 |
|---|---|---|
| B0 | GitHub Search | 纯关键字基线，对照工业现状 |
| B1 | BM25 | 标准 sparse 检索 |
| B2 | Vanilla Dense RAG | 单路向量检索 |
| B3 | Hybrid RAG | dense + sparse + rerank |
| B4 | Hybrid + 结构图（完整系统） | Dcode |

每一级独立运行同一问题集，独立报告指标。

**3.4.4 指标实现**

| 指标层级 | 实现 |
|---|---|
| Retrieval | Recall@k, MRR, nDCG（依 GT 计算） |
| Answer Quality | LLM-as-Judge（rubric 评分 + pairwise win-rate） |
| Faithfulness | Groundedness（程序化校验，见 §3.3.4） |

### 3.5 前端展示层 (Frontend)

**职责**：承载 Vision Doc §6.2 定义的代表性演示场景。

**功能清单（按优先级）**：

| 优先级 | 功能 |
|---|---|
| P0 | 仓库提交与索引状态实时展示（SSE） |
| P0 | 自然语言查询输入与流式答案展示 |
| P0 | 答案中代码引用的可跳转渲染 |
| P1 | 完整系统 vs Baseline 并列对比视图（demo 场景） |
| P2 | 代码图局部可视化 |

**技术栈**：React + Tailwind；与 odieyang.com 主作品集视觉风格一致。

### 3.6 基础设施与部署 (Infrastructure)

**职责**：

- 多租户隔离：所有 chunk / 图节点 / 任务记录均按 `repo_id` 隔离；
- 缓存：Redis 承载 embedding 缓存、工具结果缓存、查询缓存；
- 部署：Docker Compose 编排（API / Worker / PostgreSQL / Redis / Frontend），托管至 `dcode.odieyang.com`；
- 可观测性：结构化日志 + 关键指标（索引耗时、工具调用分布、答案延迟）。

---

## 4. 数据模型

### 4.1 核心实体关系

```
repos (1) ─── (N) chunks
  │
  └── (1) ─── (N) symbols ─── (M) edges
                 │
                 └── (linked) chunks
```

### 4.2 表设计概要

**repos**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | |
| `url` | TEXT | Git URL |
| `commit_sha` | TEXT | 索引时锁定的 commit |
| `status` | ENUM | queued / cloning / parsing / embedding / graphing / ready / failed |
| `progress` | INT | 0–100 |
| `error` | TEXT NULL | 失败原因 |
| `created_at`, `updated_at` | TIMESTAMP | |

**chunks**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | |
| `repo_id` | UUID FK | |
| `file_path` | TEXT | 相对路径 |
| `chunk_type` | ENUM | function / method / class / module_doc |
| `parent_symbol` | TEXT NULL | 所属类（如有） |
| `symbol_name` | TEXT | 函数 / 类名 |
| `signature` | TEXT NULL | 函数签名 |
| `start_line`, `end_line` | INT | |
| `imports` | JSONB | 该 chunk 所在文件的 import 列表 |
| `content` | TEXT | 代码文本 |
| `embedding` | VECTOR(N) | 向量列；N 依模型确定 |
| `tsv` | TSVECTOR | 用于 BM25 / 全文检索 |

索引：`(repo_id, file_path)`、HNSW on `embedding`、GIN on `tsv`。

**symbols**（代码图节点）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | |
| `repo_id` | UUID FK | |
| `qualified_name` | TEXT | 形如 `flask.app.Flask.run` |
| `kind` | ENUM | function / class / method / module |
| `file_path` | TEXT | |
| `line` | INT | |
| `chunk_id` | UUID FK NULL | 关联到对应 chunk |

索引：`(repo_id, qualified_name)` UNIQUE。

**edges**（代码图边）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | |
| `repo_id` | UUID FK | |
| `source_id` | UUID FK → symbols | |
| `target_id` | UUID FK → symbols | |
| `edge_type` | ENUM | calls / imports / inherits / references |
| `source_line` | INT | 边发生的位置 |

索引：`(repo_id, source_id, edge_type)`、`(repo_id, target_id, edge_type)`（反向查找用）。

### 4.3 Redis 键命名规范

| 模式 | 用途 | TTL |
|---|---|---|
| `embed:{model_id}:{sha256(text)}` | embedding 缓存 | 永久 |
| `tool:{tool_name}:{repo_id}:{args_hash}` | 工具结果缓存 | 24h |
| `query:{repo_id}:{query_hash}` | 完整查询缓存 | 1h |
| `job:{repo_id}` | 索引任务状态 | 任务完成后保留 7 天 |

---

## 5. 接口契约

> 以下契约为团队成员间的硬约束。任何字段名、类型、错误码变更需经接口拥有者（见 §8）评审。

### 5.1 索引 API

**`POST /api/v1/repos`**

```json
Request:  { "url": "https://github.com/pallets/flask.git" }
Response: 202 Accepted
{
  "repo_id": "uuid",
  "status": "queued"
}
```

**`GET /api/v1/repos/{repo_id}/status`**

```json
Response: 200 OK
{
  "repo_id": "uuid",
  "status": "embedding",
  "progress": 47,
  "stages": {
    "cloning": "done",
    "parsing": "done",
    "embedding": "in_progress",
    "graphing": "pending"
  },
  "error": null
}
```

### 5.2 检索 API（内部，供 Agent 调用）

**`search(repo_id, query, k=10) → List[Chunk]`**

```json
[
  {
    "chunk_id": "uuid",
    "file_path": "src/flask/app.py",
    "symbol_name": "Flask.run",
    "start_line": 870, "end_line": 920,
    "content": "...",
    "score": 0.87,
    "score_components": { "dense": 0.81, "sparse": 0.62, "rerank": 0.87 }
  }
]
```

**`find_definition / find_references / get_dependencies / get_file_outline`** 返回结构统一为 `Location` 数组：

```json
[
  {
    "symbol": "Flask.run",
    "file_path": "src/flask/app.py",
    "line": 870,
    "chunk_id": "uuid"
  }
]
```

### 5.3 Agent SSE 输出格式

服务端事件流，每个事件类型与负载固定：

```
event: thought
data: { "step": 1, "content": "..." }

event: tool_call
data: { "step": 1, "tool": "search_code", "args": {...} }

event: tool_result
data: { "step": 1, "tool": "search_code", "result_summary": "..." }

event: citation
data: { "symbol": "Flask.run", "file_path": "...", "line": 870, "verified": true }

event: partial_answer
data: { "delta": "..." }

event: final_answer
data: { "answer": "...", "citations": [...], "groundedness": 1.0 }

event: error
data: { "code": "TOOL_TIMEOUT", "message": "..." }
```

### 5.4 评测协议

评测脚本以 §5.1–§5.3 为消费方，对 B0–B4 各 Baseline 调用统一接口；结果以以下格式落盘：

```
results/{run_id}/
  ├── config.json              # baseline 标识 / 模型版本 / 问题集版本
  ├── per_question.jsonl       # 每题的检索结果 + 答案 + GT 比对
  ├── metrics.json             # Recall@k / MRR / nDCG / Win-Rate / Groundedness
  └── taxonomy_breakdown.json  # L1 / L2 / L3 分层指标
```

---

## 6. 非功能性需求 (NFR)

| 编号 | 类别 | 需求 |
|---|---|---|
| NFR-1 | 索引性能 | 单仓库（≤50k LOC）端到端索引时间 ≤ 30 分钟（含 embedding） |
| NFR-2 | 查询延迟 | Agent 首字节响应（TTFB）≤ 3 秒；中位完成时间 ≤ 20 秒 |
| NFR-3 | 多租户隔离 | 任一查询路径不得返回非请求 `repo_id` 范围内的数据 |
| NFR-4 | 答案可验证性 | Groundedness ≥ 95%（与 Vision Doc 验收标准一致） |
| NFR-5 | 可观测性 | 全部 API 与 worker 阶段须有结构化日志；关键计数器（索引耗时、工具调用次数、缓存命中率）须可读取 |
| NFR-6 | 成本约束 | 单次端到端查询的外部 API 成本（生成 + 重排）≤ $0.05；embedding 走自托管 |
| NFR-7 | 部署可重现 | 系统须可通过单一 `docker compose up` 在本地完整启动 |

---

## 7. 技术选型

| 类别 | 选型 | 备选 / 备注 |
|---|---|---|
| API 框架 | FastAPI | 复用 ETHIS SSE 经验 |
| Agent 框架 | LangGraph | 状态机表达力优于纯 ReAct 实现 |
| 静态分析 | tree-sitter（切块） + jedi（图） | jedi 直接提供 def / ref，避免自造调用图 |
| 向量库 | PostgreSQL + pgvector | 与代码图同库，避免独立向量服务 |
| 消息队列 | RabbitMQ（首选）/ Redis Streams（备选） | 复用 Nexus 队列经验 |
| Embedding 模型 | 自托管代码 embedding（jina-code / bge-code 类，开工前实测确定） | 通用 text-embedding 作为消融实验对照 |
| Reranker | bge-reranker（自托管）/ Cohere rerank API | 二选一 |
| Judge 模型 | 商业 LLM API（开工前评估稳定性） | 第 1 周内完成 judge 与人工判断的相关性抽测 |
| 前端 | React + Tailwind | 与 odieyang.com 风格一致 |
| 容器化 | Docker Compose | 部署目标：`dcode.odieyang.com` |

---

## 8. 团队组织与职责分工

### 8.1 角色与负责范围

| 角色 | 负责人 | 主负责组件 | 接口拥有 |
|---|---|---|---|
| Tech Lead / Indexing & Agent Owner | Odie | §3.1, §3.3, 架构集成 | §5.1, §5.3 |
| Retrieval & Infra Owner | P2 | §3.2, §3.6, §4 | §5.2 |
| Evaluation & Frontend Owner | P3 | §3.4, §3.5 | §5.4 |

Tech Lead 同时负责组件间集成与冲突仲裁。

### 8.2 职责矩阵（RACI 简化版）

| 工作项 | Odie | P2 | P3 |
|---|---|---|---|
| 数据模型设计（§4） | A | R | C |
| 索引管线实现（§3.1） | R | C | I |
| 检索与图 API（§3.2, §5.2） | C | R | C |
| Agent 编排（§3.3） | R | C | C |
| 评测系统（§3.4） | C | I | R |
| 前端（§3.5） | I | I | R |
| 基础设施 / 部署（§3.6） | C | R | I |
| 集成测试 | R | R | R |

R = Responsible, A = Accountable, C = Consulted, I = Informed

### 8.3 关键同步点

下列接口契约的冻结时间为项目能否按期交付的硬约束：

| 同步点 | 截止时间 | 涉及方 | 冻结产物 |
|---|---|---|---|
| S-1 | 第 1 周末 | Odie + P2 | §4 数据模型 + §5.1 索引 API |
| S-2 | 第 2 周中 | Odie + P2 | §5.2 检索 API |
| S-3 | 第 2 周末 | Odie + P3 | §5.3 Agent SSE 格式 |

任一同步点延迟将触发 §9.3 降级路径评估。

---

## 9. 里程碑与排期

### 9.1 总体排期

| 周次 | 里程碑 | Exit Criteria |
|---|---|---|
| W1 | **M1 — 数据通路打通** | 目标仓库经索引管线完整写入数据库；§4 数据模型冻结；§5.1 接口实现并通过冒烟测试 |
| W2 | **M2 — 端到端可问答** | §3.2、§3.3 完成；可对至少 5 个示例问题端到端产出带引用的答案；§5.2、§5.3 冻结 |
| W3 | **M3 — 评测可复现** | B0–B4 全部 Baseline 在问题集上完成至少一轮跑分；指标产出符合 §5.4 格式；UI 主路径可用 |
| W4 | **M4 — 上线与交付** | 部署至 `dcode.odieyang.com`；最终评测结果产出；技术报告 / README / 架构图完成 |

### 9.2 里程碑准入与准出

每个里程碑必须满足前一里程碑的 Exit Criteria 方可启动；任一 Exit Criteria 未达成不得跨周。

### 9.3 降级路径

按 Vision Doc §8 定义的 P0–P3 优先级执行降级。本文档层面的具体降级动作：

- **若 W1 延期**：削减 §3.6 中多租户隔离的实现复杂度，简化为单租户演示部署；
- **若 W2 延期**：削减 §3.3.2 工具清单中的 `list_directory`、`grep`，保留与 H1 验证直接相关的核心工具；
- **若 W3 延期**：削减 §3.5 前端 P1/P2 功能；削减 B0、B1 中较弱基线的运行（保留 B2、B3 对 B4 的对照）。

---

## 10. 风险登记

| 编号 | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R-1 | Embedding 模型在 Python 代码上的效果不达预期 | 检索精度不足以支撑 H1 验证 | 第 1 周完成至少 2 个候选模型的对比抽测 |
| R-2 | LLM-as-Judge 与人工判断相关性不可接受 | 答案质量指标不可信 | 第 1 周内完成 20 题人工 vs Judge 抽测；若相关性 < 0.6 改用 pairwise + 人工抽检兜底 |
| R-3 | 评测问题集 Ground Truth 质量不足 | H1 结论不稳健 | 三种来源混合构造；保留独立人工抽审环节 |
| R-4 | jedi 在目标仓库上的解析失败率过高 | 代码图不完整 | 第 1 周对候选仓库做解析覆盖率验证；选择覆盖率最高者作为主目标 |
| R-5 | 同步点延迟 | 集成链路阻塞 | §8.3 同步点延迟自动触发当日跨角色会议 |

---

## 11. 待决策事项 (Open Decisions)

下列事项需在项目执行前或第 1 周内闭环：

| 编号 | 事项 | 决策截止 | 负责人 |
|---|---|---|---|
| OD-1 | 主目标仓库（requests / flask / fastapi 中选一） | W1 周一 | Odie |
| OD-2 | Embedding 模型最终选型 | W1 周三 | P2 |
| OD-3 | Reranker：自托管 vs 商业 API | W1 周末 | P2 |
| OD-4 | Judge 模型选型与稳定性验证结论 | W1 周末 | P3 |
| OD-5 | 项目域名与代码仓库可用性确认 | W1 周一 | Odie |

---

*本文档为执行层基线。实施过程中产生的接口、模式、选型变更须以 PR 形式更新本文档并经接口拥有者确认。*