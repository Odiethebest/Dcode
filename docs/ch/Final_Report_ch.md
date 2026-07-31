# Dcode 最终报告

> **英文版为权威。** 本文是唯一仍在维护的中文文档；其余中文文档已归档至
> [`docs/archive/ch/`](../archive/ch/README.md)。若本文与
> [`docs/en/Final_Report.md`](../en/Final_Report.md) 有出入，以英文版为准。
>
> 保留本文的理由是结构性的：它是唯一包含**生成块**的中文文档，数字由
> `scripts/sync_eval_artifacts.py` 从 `results/eval-h1-bm25-2026-07-30/`
> 直接写入，`make check`
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

这份正式快照已经覆盖真正的 BM25 与 server-owned evidence ID。固定题集
全部是英文、单轮、非数学问题，因此它不能替代多轮、中文回答和 KaTeX 的
专项测试；这些交互能力仍以单元测试和集成 smoke 为证据。

<!-- BEGIN generated: eval-suite-metrics -->

| 基线 | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` BM25 稀疏检索 | 0.396 | 0.361 | 0.311 | 1.000 |
| `B2` 稠密 RAG | 0.474 | 0.325 | 0.333 | 1.000 |
| `B3` 混合 + 重排 | 0.526 | 0.625 | 0.519 | 1.000 |
| `B4` Dcode（混合 + 调用图 + agent） | 0.526 | 0.625 | 0.519 | 1.000 |

数据来源：`results/eval-h1-bm25-2026-07-30/` · 裁决写盘于 2026-07-30 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · 合成 gpt-4o-mini

该日期是**已提交的 provenance，而非 harness 输出** —— harness 完全不写时间戳。其观测依据与限制见 `results/eval-h1-bm25-2026-07-30/provenance.json`。

<!-- END generated: eval-suite-metrics -->

H1 判定：

<!-- BEGIN generated: eval-h1-verdict -->

**结论: `unsupported`**

仅当 B4 在 **L2 与 L3 上同时**比 B2 和 B3 都高出至少 `0.050` composite 分，H1 才算被支持。

| 层级 | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | 是否达标 |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` 跨文件 | 8 | 0.448 | 0.623 | 0.623 | +0.174 | +0.000 | 否 |
| `L3` 架构级 | 3 | 0.315 | 0.306 | 0.306 | −0.009 | +0.000 | 否 |

<!-- END generated: eval-h1-verdict -->

按题目层级的 Recall —— 真正成立的那道阶梯：

<!-- BEGIN generated: eval-level-ladder -->

| 层级 | n | `B1` Recall@5 | `B2` Recall@5 | `B3` Recall@5 | `B4` Recall@5 |
|---|---:|---:|---:|---:|---:|
| `L1` 单跳 | 5 | 0.600 | 1.000 | 1.000 | 1.000 |
| `L2` 跨文件 | 8 | 0.354 | 0.292 | 0.396 | 0.396 |
| `L3` 架构级 | 3 | 0.167 | 0.083 | 0.083 | 0.083 |

<!-- END generated: eval-level-ladder -->

### 如何诚实地读这组数

- **H1 未被支持**。B4 只在跨文件题上越过了对稠密 RAG 的 +0.05 门槛，其余都没有。门槛在跑之前就定死，之后没动过。
- **当前结论不依赖答案合成噪声**。B3 与 B4 被计分的检索列表完全相同，
  两者 groundedness 也都达到上限，因此 composite 打平。在这套评分下，
  随机换一次答案也不可能让 B4 对 B3 产生要求的正 margin。旧的九次
  citation 实验仍作为历史协议记录保留，但不用于替当前 evidence-ID 路径
  背书。
- **修正后的 BM25 已被完整测量**。本轮记录了公式、tokenizer、字段、参数和
  corpus revision。B1 相比旧词法快照明显改善，hybrid 在全套和 L2 上更强；
  但各层级并非单调阶梯。
- **B4 在本轮通过 groundedness 护栏**。server-owned evidence ID 让本轮答案
  保持有引用且没有 redaction marker，而 groundedness 仍按 redact 前草稿计分，
  没有为了得到好看数字而放松指标。单次通过不代表未来每次都必然通过。
- **L3 统计上很脆**。n=3，一道题就能拉动均值，显著性无法计算。稀疏 `B1`
  反而拿到全场最高的 L3 recall —— 三道题上这更像一次幸运的字面命中，
  不是 BM25 理解了架构的证据。L3 两个方向都不该读。

### 为什么 B4 在已记录的运行里赢不了 B3

**B4 在 2026-07-30 协议下被计分的检索，构造上就和 B3 完全相同** —— harness 度量的那次 `retrieve()` 在两个 rung 里是同一个混合检索，这就是那两行检索指标逐位相同的原因。调用图工具在更晚才触发，**在 agent 的答案内部**，而当时的 harness 计分的是更早的检索。于是差异化能力对 Recall / MRR / nDCG 完全不可见，B4 唯一能和 B3 拉开差距的通道只剩 groundedness；本轮该项也在上限处打平。

在那套评分下，**无论调用图做得多好，B4 都赢不了 B3**。

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
  groundedness 为 `1.0`。这是独立于完整评测的单题端到端 smoke。

复现流程见 [docs/en/Operations.md](../en/Operations.md)。

## 迭代历史

上一版报告设定过一组重开条件，**它们已经达成**，所以记录在此而不是删掉 —— 预注册门槛的意义就在于能看到它被检验时发生了什么。

**第一组条件（已达成）**：用真实 code embedding + 匹配的 `EMBEDDING_DIM` 重新索引、启用并记录 reranker、在同一套件上重跑 B1–B4。

**那次跑出了什么**：stub 快照曾让 B2/B3/B4 数值完全相同（stub 稠密检索返回空，三者退化到同一条稀疏路径）。换上真实模型后基线分开了，混合阶梯浮现出来 —— 这是 stub 那次掩盖掉的真实结论。H1 依然 unsupported，但原因完全不同，而且信息量大得多。

**它暴露出的新限制**：基线终于分开之后，才看得出 B4 被计分的检索和 B3 是同一次调用，于是调用图 —— 整个假设本身 —— 从来没有被计分。第一次跑不可能揭示这一点，因为那时 B3 和 B4 因为无关的原因本就相同。**正是达成了第一组条件，才让真正的障碍变得可见。**

**第一组补充条件（2026-07-30 已达成）**：把旧 sparse heuristic 换成可记录的
Okapi BM25，并让 server-owned evidence ID 路径完整跑完 B1–B4。当前快照就是
这次运行；B1 与 groundedness 都改善了，但 B4/B3 的计分结构没有改变。

## H1 结论

在完整真实模型运行下，**H1 仍未被支持** —— margin 见上方生成的判定表，直接读自 `h1_report.json`。

这个结论不再局限于"被抑制的基线"：真实 embedding 与真实 reranker 都用上了，基线也如预期分开了，B4 依然没过线。改变的是**原因** —— 障碍现在是"harness 度量了什么"这个已被诊断的缺口，而不是 stub 模型的假象。

### 第二组重开条件（已批准，部分实现）

当前分支已经完成第 1 项以及 B3/B4 的共享生成控制；第 2 项仍需人工评审后才能落地。尚未用新协议完整重跑 H1，因此上面的已提交结论仍然有效。

1. **已实现——按 B4 的最终证据集计分**：定义为附在最终答案上的**已验证**引用（图走完之后系统真正敢站在后面的证据）。groundedness verifier 会把解析后的 chunk ID 与证据来源附在 citation 事件上；harness 过滤 verified 引用、按 chunk 保留首次出现去重，再送进**同一套**指标函数、同一份 GT、同一个 `k`、同一个门槛。包括 MRR 在内，所有正式指标都只看前 `k` 条，避免第 6 条引用获得 B3 top-5 没有的机会。每题并排记录 candidate、final evidence、official 三套字段，以及结构工具新增的 GT 命中，使改动可审计。

   B2/B3 保留完整 top-5（它们的最好情况）。B4 的证据集常常少于 5 条，因此它拿到的命中机会**比 B3 更少**。这个不对称是**刻意让 B4 更难**：它只能靠调用图更精准或更靠前地把 GT 证据顶上来才能赢，而这恰好就是待验证的能力。修正选在对自己更不利的方向，因为那个方向更真实。

2. **待完成——扩充 L3**：从 3 题扩到约 12 题，覆盖不同的跨模块流程，GT 由代码结构推导并验证能在索引里解析到，在重跑之前提交。草拟题目必须过人工评审，评审的是**架构覆盖是否公平、GT 是否诚实地源自代码** —— 明确**不**筛"B4 能不能答得上"。

3. **groundedness 的算法一个字不改**。把它改成只统计 redact 之后引用的
   “显而易见修法”是陷阱：那会给构造上必然全部已验证的集合打分，
   groundedness 会平凡地趋近 1.0，并可能因表面变化翻转 H1。当前实现已经
   改用 server-owned evidence IDs；这是系统 contract 的独立改动，不是度量
   改动，且已在当前完整运行中单独记录。评分规则保持不变。

扩题使下一次运行成为一次**全新的预注册**：扩充后的题集与修正后的评分，都在看到任何数字之前固定下来。

### 长期承诺

- 门槛、题集、指标定义在跑之前固定，跑完之后不动。
- 当被度量的输出客观上错了，我们改**度量什么**；我们不改通过标准。
- 两种结果都会公布。修正评分若过线，那是靠"度量了正确的东西"赢来的；若不过，本文就会写"即使把图的贡献算进去，B4 仍未过线"。
- 目标是**真实的判定**，不是通过的判定。一个带着诊断原因和精确重开条件的诚实零结果，比一个调出来的通过更有说服力。

## 当前未完成项

- 最终 verified evidence 评分已经实现但尚未完整重跑；在看到新数字之前，
  仍需把 L3 扩到约 12 题并完成人工评审。
- B0 仍需要外部 provider token；judge / pairwise 指标仍是 stub。
- migration 已加入 `index_runs` 与 `repos.current_index_run_id`，但 ORM 和
  worker 尚未写入或暴露这条 provenance 记录。
- workbench 缺少 screen-reader live region；TypeScript API contract 仍是手工镜像。
- `dcode.odieyang.com` 尚未解析，production Compose 仅做过本地验证。

复现见 [Operations.md](../en/Operations.md)。
