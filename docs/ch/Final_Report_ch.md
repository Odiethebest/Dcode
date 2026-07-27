# Dcode 最终报告

> ⚠️ 交接快照，可能滞后于 `docs/en/`；以英文文档为准（en/ is the source of truth）。

## 总结

Dcode 是一个面向代码仓库理解的结构感知检索系统，包含四个运行界面：

- 异步索引：`POST /api/v1/repos` 到 worker pipeline；
- internal retrieval 和 graph API；
- 带 grounded citations 的 SSE agent 回答；
- evaluation harness 和 Compare UI。

截至当前实现，仓库已经交付完整的本地 vertical slice：

- Python 仓库索引管线；
- retrieval 和 graph lookup endpoint；
- 可选的 embedding 与 reranker sidecar；
- agent tool orchestration；
- groundedness 校验；
- React frontend；
- committed evaluation snapshot。

## 已实现能力

| 区域 | 状态 |
|---|---|
| API gateway | 已实现 repo submission、status、query SSE、internal routes |
| Worker | 已实现 clone、parse、chunk、embed、graph、state transition |
| Retrieval | 已实现 sparse、dense sidecar path、reranker sidecar path |
| Graph | 已实现 symbols、imports、best-effort calls |
| Agent | 已实现 LangGraph loop、tools、groundedness、SSE |
| Frontend | 已实现 Index、Query、Compare |
| Eval | 已实现 baseline runner、metrics、result snapshot |

## 当前评测状态

当前 committed evaluation snapshot 显示 H1 仍为 **unsupported**。这不是实现失败，而是当前受控题集下的真实结论。

已知限制：

- 当前题集规模较小；
- B1/B2/B3/B4 的 retrieval path 需要进一步拆分；
- recorded suite 尚未用 real embedding/reranker sidecar 完整刷新；
- judge 和 pairwise scoring 还没有接入最终判定。

## 集成状态

Yuxin(Lacey)Liang 完成 retrieval 与 graph stack 后，本仓库已经完成 agent 侧 smoke：

- sidecar 模式使用 Jina v2 embedding 和 BGE reranker；
- 数据库使用 768 维 embedding；
- `psf/requests` 可重新索引；
- `/internal/search` 返回 dense 和 rerank score components；
- `find_references(symbol=send)` 返回真实调用方；
- `/api/v1/query` 可走 agent query flow。

复现流程见 [docs/en/Sidecar_Smoke.md](../en/Sidecar_Smoke.md)。

## 后续工作

下一步应优先完成：

1. 用 real sidecar 配置刷新 evaluation suite；
2. 扩大问题集；
3. 拆分 baseline retrieval path；
4. 更新 frontend eval snapshot；
5. 基于新结果重新判断 H1。

## H1 结论

当前 committed `results/eval-suite/` 快照下，**H1 仍未被支持**。验收规则：B4 需在 L2 与 L3 上同时比 B2 和 B3 高 ≥ `0.05` composite；实测四项 margin 均为负（L2 对 B2/B3 均 `-0.0125`，L3 均 `-0.0333`），故未通过。

该结论仅限于"真实 embedding/reranker 评测**之前**"的快照：本地默认 stub embedding + identity rerank（故 B2/B3/B4 检索完全相同）、planner/synthesis 为规则化——H1 想验证的臂被结构性抑制。它是有效的工程基线，而非假设的证据。

**重开 H1 需**：用真实 code embedding + 匹配的 `EMBEDDING_DIM` 重新索引、启用并记录 reranker、隔离 baseline 检索路径、按需加深 graph 边、重跑同一套件（或更强的版本化后继）。在此之前，诚实结论保持 **unsupported**。复现见 [Sidecar_Smoke.md](../en/Sidecar_Smoke.md)。
