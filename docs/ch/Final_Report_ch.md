# Dcode 最终报告

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
