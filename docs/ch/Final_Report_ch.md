# Dcode 最终报告

> **英文版为权威。** 本文是唯一仍在维护的中文文档；其余中文文档已归档至
> [`docs/archive/ch/`](../archive/ch/README.md)。若本文与
> [`docs/en/Final_Report.md`](../en/Final_Report.md) 有出入，以英文版为准。
>
> 保留本文的理由是结构性的：它是唯一包含**生成块**的中文文档，数字由
> `scripts/sync_eval_artifacts.py` 从 `results/eval-real/` 直接写入，`make check`
> 会在漂移时失败 —— 也就是说关键数字不可能悄悄过期。

> 本文已同步到 2026-07-30 的当前分支状态；英文文档仍是最终 source of truth。

## 总结

Dcode 是一个面向代码仓库理解的结构感知检索系统，由以下运行层面组成：

- 异步索引：`POST /api/v1/repos` 到 worker pipeline；
- internal retrieval 和 graph API；
- 带 grounded citations 的 SSE agent 回答；
- `/workbench` 探索界面、`/` 落地页、`/methodology` 评测页和 `/preview` 组件页；
- 离线 evaluation harness。

截至当前实现，仓库已经交付完整的本地 vertical slice：

- Python 仓库索引管线；
- retrieval 和 graph lookup endpoint；
- 可选的 embedding 与 reranker sidecar；
- agent tool orchestration；
- groundedness 校验；
- 支持多轮 follow-up、中文/英文 caller/callee 路由及同语言回答；
- 支持 KaTeX 数学公式和可点击的真实源码引用；
- React frontend 与品牌 favicon；
- committed evaluation snapshot。

## 已实现能力

| 区域 | 状态 |
|---|---|
| API gateway | 已实现 repo submission、status、query SSE、source/neighbors inspector routes；query 支持有界 history |
| Worker | 已实现 clone、parse、chunk、embed、graph、state transition |
| Retrieval | 已实现真正的 Okapi BM25、dense、默认 2:1 加权 RRF 及 reranker sidecar path |
| Graph | 已实现 symbols、imports、best-effort calls，以及保留 unresolved source calls 的双向查询 |
| Agent | 已实现 10 个工具、multi-turn contextualization、双语路由、server-owned evidence IDs、groundedness 与 SSE |
| Frontend | 已实现 `/`、`/workbench`、`/methodology`、`/preview`，并支持安全 Markdown 与 KaTeX |
| Eval | 已实现 B0–B4 runner、分层 metrics、result snapshot；新运行会记录 BM25 参数与 corpus revision |

## 当前评测状态

已在**完整真实模型**下测量（Jina v2-base-code 768 维 + BGE reranker v2-m3 + gpt-4o-mini），结论 **unsupported**。这不是实现失败，而是当前受控题集与当前评分方式下的真实结论。

> 本节所有数字由 `scripts/sync_eval_artifacts.py` 从结果目录生成，非手工转录；`make check` 会在两者不一致时失败。

这份正式快照早于当前真正的 BM25、server-owned evidence ID、多轮上下文、
同语言回答和 KaTeX 展示路径。它仍是已提交的 H1 结论，但不能被解释成对
这些 2026-07-30 新行为的完整重测；后者目前只有单元测试和集成 smoke。

<!-- BEGIN generated: eval-suite-metrics -->

| 基线 | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` 旧版词法启发式检索 | 0.214 | 0.221 | 0.204 | 1.000 |
| `B2` 稠密 RAG | 0.474 | 0.325 | 0.333 | 1.000 |
| `B3` 混合 + 重排 | 0.542 | 0.596 | 0.508 | 1.000 |
| `B4` Dcode（混合 + 调用图 + agent） | 0.542 | 0.596 | 0.508 | **0.916** ⚠️ 低于 0.95 护栏 |

数据来源：`results/eval-real/` · 裁决写盘于 2026-07-28 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · 合成 gpt-4o-mini

该日期为**回溯恢复，非 harness 记录** —— harness 完全不写时间戳。恢复方式及其不能证明的部分见 `results/eval-real/provenance.json`。

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
- **这个判定扛得住重跑噪声，而它此前从未被这样检验过**。答案合成是随机的，上面每个数字都只来自单次跑。另外六次 B4 跑 —— 三次用与本次完全相同的合成代码、三次改了引用提示词，全部在同一会话、同一索引上完成 —— 界定了一次重复的代价。六次的 Recall@5 / MRR / nDCG@5 **逐位相同**，而 B3 的 groundedness 每题都是 1.000，所以整个 margin 分布只来自 B4 的合成，并且恰好等于该层 groundedness 散布的四分之一。这样量出来，距 +0.05 门槛的距离在四个「臂 × 层级」组合里**最不利的一个也有 6.9 个标准差，最有利的达到 21.6 个**。合成随机性够不到这个量级，所以 `unsupported` 不是「只测了一次」的产物。设计、在看到数字之前定下的判据、以及每次跑的具体数字：[`results/b4-citation-fix-experiment.md`](../../results/b4-citation-fix-experiment.md)。那六次跑不在 `results/eval-real/` 之下，所以这里引用的两个比值是本文档唯一不被产物漂移检查覆盖的数字 —— 以该文件为准。
- **归档阶梯不能作为 BM25 验证**。它在单跳和跨文件层级上呈现出“旧版词法启发式 → 稠密 → 混合+重排”的单调顺序，但当时的 B1 实际是 `ILIKE` 加固定子串权重，不是 BM25；B3/B4 也复用了同一个 sparse 分支。必须用修正后的 BM25 对 B1–B4 整套重跑，才能重新提出更强的 hybrid 消融结论。
- **B4 的 groundedness 低于 0.95 护栏**。本报告的上一版把这个数写成 `0.95` 并描述为"贴着阈值下限"，而真实值在护栏**之下** —— 这是唯一一处旧版说得偏好听的地方，在此更正。agent 偶尔会给出通不过验证的引用；这些引用会从交付给用户的答案里剥离，所以用户读到的仍然是已验证的，但**分数刻意统计 redact 之前的草稿**，因此被大幅剥离的答案分数依然低。这是"草稿有多干净"的诚实度量，而这次掉点是对一条预注册护栏的真实未达标。**对这个数字本身的一点限定（不是对结论的限定）**：用同一份合成代码跑的四次 —— 归档那次套件跑加三次重复 —— 全部落在护栏之下，而被记录下来的那个值是四次里**最高**的；四次均值比本报告显示的值离护栏更远。所以方向是稳的，而且偏保守。但幅度不稳：被记录值所隐含的差距，与重复之间的散布大致同量级。**本文任何一处都不去量化系统低于护栏多少**，因为单次 16 题的跑支撑不了这个精度。注意这次撤回的范围很窄：「**这一次跑**得到的是被记录的那个值」依然完全成立，生成块和 UI 陈述的正是这一点；被撤回的是把那个值读成「系统所处的位置」——那是另一个主张，也恰好是读者会带走的那个。
- **L3 统计上很脆**。n=3，一道题就能拉动均值，显著性无法计算。稀疏 `B1` 反而拿到全场最高的 L3 recall —— 三道题上这几乎肯定是一次幸运的字面命中，不是旧版启发式理解了架构的证据。L3 两个方向都不该读。扩充它是下一次跑的前置条件。

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
- 2026-07-30 当前路径 smoke 中，`Who calls send?` 返回
  `src/requests/sessions.py:186` 与 `:557` 两条 verified citation，
  groundedness 为 `1.0`。这只证明单题端到端路径，不替代评测。

复现流程见 [docs/en/Operations.md](../en/Operations.md)。

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

3. **groundedness 的算法一个字不改**。这里只统计 redact 之后引用的
   “显而易见修法”是陷阱：那会给构造上必然全部已验证的集合打分，
   groundedness 会平凡地趋近 1.0，并可能因表面变化翻转 H1。当前实现已经
   改用 server-owned evidence IDs；这是系统 contract 的独立改动，不是度量
   改动。它尚未经过完整 H1 重跑，必须在下一次运行中单独记录，不能悄悄
   折进旧结论。

扩题使下一次运行成为一次**全新的预注册**：扩充后的题集与修正后的评分，都在看到任何数字之前固定下来。

### 长期承诺

- 门槛、题集、指标定义在跑之前固定，跑完之后不动。
- 当被度量的输出客观上错了，我们改**度量什么**；我们不改通过标准。
- 两种结果都会公布。修正评分若过线，那是靠"度量了正确的东西"赢来的；若不过，本文就会写"即使把图的贡献算进去，B4 仍未过线"。
- 目标是**真实的判定**，不是通过的判定。一个带着诊断原因和精确重开条件的诚实零结果，比一个调出来的通过更有说服力。

## 当前未完成项

- 按最终 verified evidence set 给 B4 计分，并在看到新数字之前扩充 L3。
- 用当前真正的 BM25 和 server-owned evidence ID 协议完整重跑 B1–B4。
- B0 仍需要外部 provider token；judge / pairwise 指标仍是 stub。
- migration 已加入 `index_runs` 与 `repos.current_index_run_id`，但 ORM 和
  worker 尚未写入或暴露这条 provenance 记录。
- workbench 缺少 screen-reader live region；TypeScript API contract 仍是手工镜像。
- `dcode.odieyang.com` 尚未解析，production Compose 仅做过本地验证。

复现见 [Operations.md](../en/Operations.md)。
