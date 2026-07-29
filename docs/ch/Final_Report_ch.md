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

已在**完整真实模型**下测量（Jina v2-base-code 768 维 + BGE reranker v2-m3 + gpt-4o-mini），结论 **unsupported**。这不是实现失败，而是当前受控题集与当前评分方式下的真实结论。

> 本节所有数字由 `scripts/sync_eval_artifacts.py` 从结果目录生成，非手工转录；`make check` 会在两者不一致时失败。

<!-- BEGIN generated: eval-suite-metrics -->

| 基线 | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` BM25 稀疏检索 | 0.214 | 0.221 | 0.204 | 1.000 |
| `B2` 稠密 RAG | 0.474 | 0.325 | 0.333 | 1.000 |
| `B3` 混合 + 重排 | 0.542 | 0.596 | 0.508 | 1.000 |
| `B4` Dcode（混合 + 调用图 + agent） | 0.542 | 0.596 | 0.508 | **0.916** ⚠️ 低于 0.95 护栏 |

数据来源：`results/eval-real/` · 记录于 2026-07-28 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · 合成 gpt-4o-mini

<!-- END generated: eval-suite-metrics -->

H1 判定：

<!-- BEGIN generated: eval-h1-verdict -->

**结论: `unsupported`**

仅当 B4 在 **L2 与 L3 上同时**比 B2 和 B3 都高出至少 `0.050` composite 分，H1 才算被支持。

| 层级 | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | 是否达标 |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` 跨文件 | 8 | 0.448 | 0.586 | 0.562 | +0.113 | −0.024 | 否 |
| `L3` 架构级 | 3 | 0.315 | 0.371 | 0.324 | +0.009 | −0.047 | 否 |

<!-- END generated: eval-h1-verdict -->

按题目层级的 Recall —— 真正成立的那道阶梯：

<!-- BEGIN generated: eval-level-ladder -->

| 层级 | n | `B1` Recall@5 | `B2` Recall@5 | `B3` Recall@5 | `B4` Recall@5 |
|---|---:|---:|---:|---:|---:|
| `L1` 单跳 | 5 | 0.200 | 1.000 | 1.000 | 1.000 |
| `L2` 跨文件 | 8 | 0.208 | 0.292 | 0.396 | 0.396 |
| `L3` 架构级 | 3 | 0.250 | 0.083 | 0.167 | 0.167 |

<!-- END generated: eval-level-ladder -->

### 如何诚实地读这组数

- **H1 未被支持**。B4 只在跨文件题上越过了对稠密 RAG 的 +0.05 门槛，其余都没有。门槛在跑之前就定死，之后没动过。
- **混合检索被证实了**。稀疏 → 稠密 → 混合+重排 在单跳和跨文件层级上是干净的单调阶梯。这个结论独立于 H1 判定，也是真正立住的发现；今天检索的赢家是 B3。
- **B4 的 groundedness 低于 0.95 护栏**。本报告的上一版把这个数写成 `0.95` 并描述为"贴着阈值下限"，而真实值在护栏**之下** —— 这是唯一一处旧版说得偏好听的地方，在此更正。agent 偶尔会给出通不过验证的引用；这些引用会从交付给用户的答案里剥离，所以用户读到的仍然是已验证的，但**分数刻意统计 redact 之前的草稿**，因此被大幅剥离的答案分数依然低。这是"草稿有多干净"的诚实度量，而这次掉点是对一条预注册护栏的真实未达标。
- **L3 统计上很脆**。n=3，一道题就能拉动均值，显著性无法计算。稀疏 `B1` 反而拿到全场最高的 L3 recall —— 三道题上这几乎肯定是一次幸运的字面命中，不是 BM25 懂架构的证据。L3 两个方向都不该读。扩充它是下一次跑的前置条件。

### 为什么 B4 现在赢不了 B3

**B4 被计分的检索，构造上就和 B3 完全相同** —— harness 度量的那次 `retrieve()` 在两个 rung 里是同一个混合检索，这就是那两行检索指标逐位相同的原因。调用图工具在更晚才触发，**在 agent 的答案内部**，而 harness 计分的是检索、不是答案。于是差异化能力对 Recall / MRR / nDCG 完全不可见，B4 唯一能和 B3 拉开差距的通道只剩 groundedness —— 而它掉了点。

在这套评分下，**无论调用图做得多好，B4 都赢不了 B3**。

准确的说法是：图的贡献**未被度量**。不是"不可见"、不是"未被验证"、更不是"它没用" —— 是 harness 从来没有看过图所贡献的那个输出。多说或少说都不准确。

## 集成状态

Yuxin(Lacey)Liang 完成 retrieval 与 graph stack 后，本仓库已经完成 agent 侧 smoke：

- sidecar 模式使用 Jina v2 embedding 和 BGE reranker；
- 数据库使用 768 维 embedding；
- `psf/requests` 可重新索引；
- `/internal/search` 返回 dense 和 rerank score components；
- `find_references(symbol=send)` 返回真实调用方；
- `/api/v1/query` 可走 agent query flow。

复现流程见 [docs/en/Sidecar_Smoke.md](../en/Sidecar_Smoke.md)。

## 迭代历史

上一版报告设定过一组重开条件，**它们已经达成**，所以记录在此而不是删掉 —— 预注册门槛的意义就在于能看到它被检验时发生了什么。

**第一组条件（已达成）**：用真实 code embedding + 匹配的 `EMBEDDING_DIM` 重新索引、启用并记录 reranker、在同一套件上重跑 B1–B4。

**那次跑出了什么**：stub 快照曾让 B2/B3/B4 数值完全相同（stub 稠密检索返回空，三者退化到同一条稀疏路径）。换上真实模型后基线分开了，混合阶梯浮现出来 —— 这是 stub 那次掩盖掉的真实结论。H1 依然 unsupported，但原因完全不同，而且信息量大得多。

**它暴露出的新限制**：基线终于分开之后，才看得出 B4 被计分的检索和 B3 是同一次调用，于是调用图 —— 整个假设本身 —— 从来没有被计分。第一次跑不可能揭示这一点，因为那时 B3 和 B4 因为无关的原因本就相同。**正是达成了第一组条件，才让真正的障碍变得可见。**

## H1 结论

在完整真实模型运行下，**H1 仍未被支持** —— margin 见上方生成的判定表，直接读自 `h1_report.json`。

这个结论不再局限于"被抑制的基线"：真实 embedding 与真实 reranker 都用上了，基线也如预期分开了，B4 依然没过线。改变的是**原因** —— 障碍现在是"harness 度量了什么"这个已被诊断的缺口，而不是 stub 模型的假象。

### 第二组重开条件（已批准，尚未实现）

1. **按 B4 的最终证据集计分**：定义为附在最终答案上的**已验证**引用（图走完之后系统真正敢站在后面的证据）。从 citation 事件里取出有序的 `(file_path, line, verified)` 三元组、过滤到 verified、保留首次出现去重、用**与 ground truth 相同的行包含规则**映射到 chunk id，再送进**同一套**指标函数、同一份 GT、同一个 `k`、同一个门槛。每题并排记录新旧两套评分以及映射到的 chunk id，使改动可审计。

   B2/B3 保留完整 top-5（它们的最好情况）。B4 的证据集常常少于 5 条，因此它拿到的命中机会**比 B3 更少**。这个不对称是**刻意让 B4 更难**：它只能靠调用图更精准或更靠前地把 GT 证据顶上来才能赢，而这恰好就是待验证的能力。修正选在对自己更不利的方向，因为那个方向更真实。

2. **扩充 L3**：从 3 题扩到约 12 题，覆盖不同的跨模块流程，GT 由代码结构推导并验证能在索引里解析到，在重跑之前提交。草拟题目必须过人工评审，评审的是**架构覆盖是否公平、GT 是否诚实地源自代码** —— 明确**不**筛"B4 能不能答得上"。

3. **groundedness 的算法一个字不改**。这里那个"显而易见的修法"是陷阱：只统计 redact 之后的引用，等于给一个构造上必然全部已验证的集合打分，groundedness 会平凡地趋近 1.0、B4 的 composite 被抬高，H1 可能因为一个纯粹表面的原因翻盘 —— 那是穿着 bugfix 外衣的 p-hacking。收紧**合成 prompt** 让模型只从白名单引用是正当的（改的是系统，不是度量），但它会移动 B4 的数字，必须作为独立改动单独汇报，绝不悄悄折进 H1 的结论，也刻意不与这次重跑捆在一起。

扩题使下一次运行成为一次**全新的预注册**：扩充后的题集与修正后的评分，都在看到任何数字之前固定下来。

### 长期承诺

- 门槛、题集、指标定义在跑之前固定，跑完之后不动。
- 当被度量的输出客观上错了，我们改**度量什么**；我们不改通过标准。
- 两种结果都会公布。修正评分若过线，那是靠"度量了正确的东西"赢来的；若不过，本文就会写"即使把图的贡献算进去，B4 仍未过线"。
- 目标是**真实的判定**，不是通过的判定。一个带着诊断原因和精确重开条件的诚实零结果，比一个调出来的通过更有说服力。

复现见 [Sidecar_Smoke.md](../en/Sidecar_Smoke.md)。
