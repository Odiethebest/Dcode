# Dcode

> 面向新人 onboarding 的**结构感知代码理解平台**：提交一个 GitHub 仓库，系统异步建立「语义索引 + 代码调用图」，通过多工具 ReAct Agent 用自然语言回答跨文件、架构层面的代码问题，并返回经程序化校验的可跳转引用。

**项目名**：Dcode（"Decode" 去一个 e 的造词）。语义层告诉你"在哪"，结构图层告诉你"谁连着谁"，Agent 带你"怎么走"。

---

## 问题

大型代码仓库的新成员入职面临持续性的认知负担。其核心信息需求是**关系（relation）查询**——某功能的端到端实现路径、某模块的上下游依赖、某符号的调用关系——而非**相似度（similarity）查询**。

现有主流方案系统性失效：

| 工具类别 | 代表 | 局限 |
|---|---|---|
| 关键字搜索 | GitHub Search、ripgrep | 仅字面匹配，无自然语言意图 |
| 扁平向量 RAG | 主流 RAG 实现 | 仅文本相似度，丢失代码间结构关系 |
| 通用聊天助手 | 一般 LLM 应用 | 无 codebase 上下文，引用幻觉率高 |

---

## 核心假设 (H1)

> **在跨文件、架构层面的代码理解任务上，结构感知索引（语义向量 + 代码调用图）与多工具 Agent 编排相结合的检索增强生成方案，相对扁平向量 RAG 与关键字搜索基线，能够在标准 IR 指标与端到端答案质量指标上取得显著且可复现的改进。**

整个项目的工程投入服务于这个**可证伪假设**。若验收指标未达成，假设被拒绝，项目结论按"假设未被支持"如实记录——不打补丁、不调整阈值。

---

## 系统能力

- **异步索引管线**：clone → tree-sitter AST 切块 → 自托管 embedding → jedi 建图 → PostgreSQL + pgvector 落库
- **混合检索**：dense（pgvector）+ sparse（BM25）双路召回 → RRF 融合 → cross-encoder 重排
- **代码图查询**：`find_definition` / `find_references` / `get_dependencies` / `get_file_outline`
- **多工具 ReAct Agent**：LangGraph 状态机，8 个 tools，单次查询上限 8 步，SSE 流式输出
- **程序化 Groundedness**：所有答案引用回查校验，硬约束 ≥ 95%（不可禁用）
- **完整 Baseline 阶梯**：B0 GitHub Search → B1 BM25 → B2 Vanilla RAG → B3 Hybrid RAG → B4 Dcode

---

## 高层架构

```
       ┌──────────┐  HTTPS/SSE   ┌──────────────────┐
       │  Client  │ ───────────▶ │ FastAPI Gateway  │
       └──────────┘              └────┬─────────┬───┘
                                      │         │
                       POST /repos    │         │  POST /query (SSE)
                                      ▼         ▼
                               ┌──────────┐   ┌──────────────────┐
                               │  Queue   │   │  LangGraph Agent │
                               │ RabbitMQ │   └────┬─────────────┘
                               └────┬─────┘        │ tool calls
                                    ▼              ▼
                              ┌──────────┐  ┌──────────────────┐
                              │  Worker  │  │ Retrieval & Graph│
                              │ AST/jedi │  │ hybrid + graph   │
                              └────┬─────┘  └────┬─────────────┘
                                   │ 写入        │ 读取
                                   ▼             ▼
                              ┌──────────────────────────────┐
                              │ PostgreSQL + pgvector + Redis│
                              └──────────────────────────────┘
```

完整架构与组件设计见 [docs/DESIGN.md](docs/DESIGN.md)。

---

## 范围

**In Scope**：Python 单语言；1–3 个中等规模主流开源 repo（候选 `requests` / `flask` / `fastapi`）；异步索引、混合检索、代码图、ReAct Agent、完整评测、Web UI。

**Out of Scope**：多语言、IDE 插件、代码生成 / 修改、实时增量索引、配置文件解析、大规模图可视化。

详见 [docs/PLAN.md §2](docs/PLAN.md#2-项目范围)。

---

## 验收摘要

| 指标 | 目标 |
|---|---|
| Retrieval (Recall@k / MRR / nDCG) | 完整系统相对每一级基线均有可观测改进，跨文件 / 架构级子集具备统计显著性 |
| Agent Pairwise Win-Rate vs 裸 RAG | > 60% |
| Groundedness | ≥ 95% |

完整验收标准与定性产出见 [docs/PLAN.md §3](docs/PLAN.md#3-验收标准)。

---

## 技术栈

| 类别 | 选型 |
|---|---|
| API | FastAPI + SSE |
| Agent | LangGraph |
| 静态分析 | tree-sitter + jedi |
| 存储 | PostgreSQL + pgvector + Redis |
| 消息队列 | RabbitMQ |
| Embedding | 自托管开源代码 embedding（jina-code / bge-code 类） |
| 前端 | React + Tailwind |
| 部署 | Docker Compose → `dcode.odieyang.com` |

详见 [docs/DESIGN.md §6](docs/DESIGN.md#6-技术选型)。

---

## 快速开始

> 骨架尚未搭建。完成后此处提供 `docker compose up` 一键启动指南、环境变量清单、Make targets 说明。

```bash
# TBD
```

---

## 项目结构

> 骨架尚未搭建。完成后此处提供目录导览（apps / packages / infra / scripts）。

```
TBD
```

---

## 文档

| 文档 | 角色 | 主要内容 |
|---|---|---|
| **[docs/DESIGN.md](docs/DESIGN.md)** | 技术权威 | 系统架构、组件设计、数据模型、接口契约、NFR、技术选型 |
| **[docs/PLAN.md](docs/PLAN.md)** | 执行权威 | 项目目标、范围、验收、优先级、团队组织、里程碑、风险、Open Decisions |

---

## License

Apache License 2.0. 见 [LICENSE](LICENSE)。
