# Dcode 最终报告

> **英文版为权威。** 本文是唯一仍在维护的中文文档；其余中文文档已归档至
> [`docs/archive/ch/`](../archive/ch/README.md)。若本文与
> [`docs/en/Final_Report.md`](../en/Final_Report.md) 有出入，以英文版为准。
>
> 保留本文的理由是结构性的：它是唯一包含**生成块**的中文文档，数字由
> `scripts/sync_eval_artifacts.py` 从 `results/eval-h1-repeat3-2026-07-31/`
> 直接写入，`make check`
> 会在漂移时失败 —— 也就是说关键数字不可能悄悄过期。

> 本文已同步到 2026-07-31 的三遍重复运行；英文文档仍是最终 source of truth。

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
| Agent | 已实现 11 个工具、multi-turn contextualization、双语路由、server-owned evidence IDs、groundedness 与 SSE |
| Frontend | 已实现 `/`、`/workbench`、`/methodology`、`/preview`，并支持安全 Markdown 与 KaTeX |
| Eval | 已实现 B0–B4 runner、分层 metrics、result snapshot；新运行会记录 BM25 参数与 corpus revision |

## 当前评测状态

已在**完整真实模型**下测量（Jina v2-base-code 768 维 + BGE reranker v2-m3 +
gpt-4o-mini），33 道题、含 `B3.5` 消融在内的五个 arm、**三遍重复取均值**，结论
**unsupported**——H1 是四项对比的合取，其中**三项通过**：架构级问题上对两个对手
分别超出门槛 3.4 倍与 4.9 倍，跨文件问题上对混合检索差 0.006。

跨三遍重复，跨文件的 margin 离散范围比门槛本身还大，**其中一遍单独判定为
supported**。引用本节任何数字之前，请先读下面「如何诚实地读这组数」。

> 本节所有数字由 `scripts/sync_eval_artifacts.py` 从结果目录生成，非手工转录；`make check` 会在两者不一致时失败。

这份正式快照已经覆盖真正的 BM25 与 server-owned evidence ID。固定题集
全部是英文、单轮、非数学问题，因此它不能替代多轮、中文回答和 KaTeX 的
专项测试；这些交互能力仍以单元测试和集成 smoke 为证据。

<!-- BEGIN generated: eval-suite-metrics -->

| 基线 | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` BM25 稀疏检索 | 0.390 | 0.563 | 0.376 | 1.000 |
| `B2` 稠密 RAG | 0.489 | 0.702 | 0.524 | 1.000 |
| `B3` 混合 + 重排 | 0.553 | 0.795 | 0.587 | 1.000 |
| `B4` Dcode（混合 + 调用图 + agent） | 0.638 | 0.882 | 0.664 | 1.000 |

数据来源：`results/eval-h1-repeat3-2026-07-31/` · 裁决写盘于 2026-07-31 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · 合成 gpt-4o-mini

该日期是**已提交的 provenance，而非 harness 输出** —— harness 完全不写时间戳。其观测依据与限制见 `results/eval-h1-repeat3-2026-07-31/provenance.json`。

<!-- END generated: eval-suite-metrics -->

H1 判定：

<!-- BEGIN generated: eval-h1-verdict -->

**结论: `unsupported`**

仅当 B4 在 **L2 与 L3 上同时**比 B2 和 B3 都高出至少 `0.050` composite 分，H1 才算被支持。

| 层级 | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | 是否达标 |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` 跨文件 | 16 | 0.579 | 0.671 | 0.715 | +0.136 | +0.044 | 否 |
| `L3` 架构级 | 12 | 0.384 | 0.462 | 0.632 | +0.247 | +0.169 | 是 |

<!-- END generated: eval-h1-verdict -->

按题目层级的 Recall —— 真正成立的那道阶梯：

<!-- BEGIN generated: eval-level-ladder -->

| 层级 | n | `B1` Recall@5 | `B2` Recall@5 | `B3` Recall@5 | `B4` Recall@5 |
|---|---:|---:|---:|---:|---:|
| `L1` 单跳 | 5 | 0.600 | 1.000 | 1.000 | 1.000 |
| `L2` 跨文件 | 16 | 0.407 | 0.494 | 0.546 | 0.619 |
| `L3` 架构级 | 12 | 0.279 | 0.271 | 0.376 | 0.512 |

<!-- END generated: eval-level-ladder -->

### 如何诚实地读这组数

- **H1 是合取命题，四项对比里三项通过，一项没过，所以整体 unsupported。**

  | | 对 `B2` 纯向量 RAG | 对 `B3` 混合+重排 |
  |---|---|---|
  | **`L3` 架构级** | **+0.247** ✅ 门槛的 4.9 倍 | **+0.169** ✅ 门槛的 3.4 倍 |
  | **`L2` 跨文件** | **+0.136** ✅ 门槛的 2.7 倍 | +0.044 ✕ 差 0.006 |

  `h1_report.json` 里的分层 `supported` 字段（预注册结构里本来就有，不是事后加的解读）
  记录为 `L3: supported`、`L2: not supported`。

- **本轮最重要的数字不是任何一个 margin，是它的离散度。** 三遍重复，代码、题集、
  索引完全相同：

  | 第几遍 | `L2` 对 B3 的 margin | 判定 |
  |---|---:|---|
  | 1 | +0.0376 | unsupported |
  | 2 | +0.0057 | unsupported |
  | 3 | **+0.0884** | **supported** |

  **三遍里有一遍单独通过。** 极差 0.083，比 0.050 的门槛本身还大。第三遍之所以过，
  是因为那一遍 B3 掉了 0.053，不是 B4 变强。如果只跑了第三遍，本文现在会写
  `supported`——用的是同一份代码。此前所有单跑的「差 0.0036」「差 0.0016」都在噪声里。

- **对 H1 原文点名的基线，两层全部通过。** H1 的表述是"优于 flat vector RAG 与
  keyword search 基线"，即 `B2` 与 `B1`。判定规则额外要求胜过 `B3`（混合检索+重排），
  这比假设文本本身更严；那道更严的栏从第一次运行起就在规则里，现在也不会挪动，
  只是需要说清楚失败的是哪一格、对手是谁。

- **L3 是站得住的结论。** 对 B3 +0.169、对 B2 +0.247，三遍各自独立通过，而且是在
  最难的一层上。这是能留下来的发现。

- **调用图有效，但不是主要贡献者。** `B3.5`（关闭图与引用工具、其余完全相同）第一次
  把两者分开：

  | | 调用图（`B4 − B3.5`） | 多步阅读（`B3.5 − B3`） |
  |---|---:|---:|
  | `L2` | +0.022 | +0.022 |
  | `L3` | +0.023 | **+0.147** |

  两轮之前图还是**负贡献**，现在稳定为正——但在架构题上，agent 的多步取证价值约为
  图的六倍。没有 `B3.5`，这 +0.147 会被当成图的功劳报出去。

- **composite 改为三项，而且这并没有救回结论。** groundedness 在四轮未达标之后被移除；
  由于它在所有 arm 上恒为 1.000，移除等于把所有 margin 乘以 4/3，也就是把门槛降到
  0.0375。完整披露见上文。四项口径同样记录在每个 `h1_report.json` 的 `four_term` 里，
  在本轮同样是 `unsupported`（L2 为 +0.033）。**降低的门槛什么也没买到，结论不依赖它。**

- **真正能解决 L2 的是什么。** 缺口 0.0061，而重复间标准差是 0.034。靠重复把这么小的
  差异测出来需要约 100 遍。出路是增加 L2 题量——16 道对这个效应量来说太少——而不是
  继续调参、也不是继续加重复。

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
Okapi BM25，并让 server-owned evidence ID 路径完整跑完 B1–B4。B1 与
groundedness 都改善了，但 B4/B3 的计分结构没有改变。该快照现已被取代。

**第二组条件（2026-07-31 已达成）**：按 B4 的最终验证证据计分、让 B3 走同一条
agent 生成路径、把 L3 从 3 扩到 12。那一次运行是
`results/eval-h1-l3x12-2026-07-31/`，采用混合的 `final_verified_evidence_v1`
规则，**现已被当前的重复运行取代**——本小节的每个数字描述的都是那一次，不是上方
记录的判定。

**那次运行显示了什么。** 上一轮诊断出的障碍消失了：B4 被计分的证据不再是 B3 的
检索列表，图终于能够进入指标。那一轮 B4 在 L2 上过线、在 L3 上差 0.005——同时暴露
出三件此前任何一轮都不可能看见的事：其一，**这条修正自己的理由是错的**，把 B4 按
更小的证据集计分曾被预注册为"让它更难"，实测是优势；其二，**产生 B4 margin 的不是
图**，那一轮结构性证据只带来 33 题中 3 题的 4 个新 GT 命中；其三，**结论依赖一条
只为一个 arm 预注册过的评分规则**，把同一规则套到 B3 上，L3 就从不过变成过。

## H1 结论

在完整真实模型运行下，**H1 仍未被支持** —— margin 见上方生成的判定表，直接读自
`h1_report.json`。`L3` 对两个对手都过线；`L2` 对 B2 过线、对 B3 差 0.006。第三条
已经不再成立：在 `uniform_final_verified_evidence_v2` 下每条 agent arm 用同一条
规则计分，B3 不再翻转结论。

这个结论不再局限于"被抑制的基线"，也不再局限于"无法度量的比较"：真实 embedding、
真实 reranker、每条 agent arm 共享的生成路径与**同一条**评分规则、以及能隔离调用图
的 `B3.5` 消融都已到位，B4 依然没有同时过两个层级。改变的还是**原因**——障碍不再是
"harness 看不见图"，也不再是"两个 arm 用了不同的评分规则"，而是"图的贡献很小，且
决定结论的那个 margin 小于它自己的重复间波动"。

### 第三组条件——结果

在运行之前定死，与前两组同样的做法。**第 1–4 项已实现并已运行：上方记录的判定就是
在这些条件下跑出来的。** 第 5、6 项见下。

1. **已实现——所有 arm 用同一条评分规则**：正式指标是**已验证最终证据**，对 `B2`、
   `B3`、`B3.5`、`B4` 一视同仁，协议 id `uniform_final_verified_evidence_v2`。
2. **已实现——B2 的 `dense_only` agent 模式**：B2 现在与 B4 共享同一个模型、prompt、
   引用协议与 groundedness 校验，只是检索走纯稠密。它的 groundedness 因此是测量值，
   而不再是常量 `1.0`。检索模式走 `search_code` 的**工具参数**而非环境状态——工具
   缓存键是 `(tool, repo_id, args)`，放在 args 之外会让两条 arm 撞进同一个缓存条目。
3. **已实现——`B3.5` 诊断 arm**：同一 agent 与 `read_file` 循环，关闭调用图与引用
   工具。`B4 − B3` 度量整个 agent 系统，`B4 − B3.5` 才度量调用图本身，也就是真正的
   假设。**仅作诊断，不进入通过标准**——把一个 arm 加进判定规则就是改通过标准。
4. **已实现——跨来源证据的统一排序**：图与引用命中先按 `chunk_id` 补全源码，再由
   同一个 cross-encoder 对并集打分，上下文预算对每条 arm 是同一个数。证据**来源被
   记录但刻意不进入排序**——可调的图先验就是在评测集上拟合超参。`graph_distance`
   本身并未计算，真正记录下来的诊断量是来源（origin）。
5. **把 L3 提到 n ≈ 22**，让单题权重低于 0.05 的判定 margin，并且要靠**第二个语料**
   （已索引的 `encode/httpx`）而不是在 Requests 里继续堆题。前置条件是让每道题绑定
   自己的仓库：harness 目前只记录一个 `repo_id_override`、只读一个 `index_revision`。
   **仍未完成。**
6. ~~**提高 `max_steps` 或收窄扩张**~~ **——已在记录运行之前完成。** B4 曾把 8 步
   预算打满，`get_file_outline` 实际触及不到。`max_steps` 现为 `14`（`2379c39`，
   早于记录运行），遍历由规划器结束而不是被上限截断。

### 长期承诺

- 门槛、题集、指标定义在跑之前固定，跑完之后不动。
- 当被度量的输出客观上错了，我们改**度量什么**；我们不改通过标准。
- 两种结果都会公布，被证伪的预注册预测同样公布。本轮就证伪了我们自己的一条，已记录在上。
- 当两条都站得住的评分规则给出不同结论时，预注册的那条是结论，另一条公布在旁边。
  事后挑赢的那条这个选项不存在。
- 目标是**真实的判定**，不是通过的判定。一个带着诊断原因和精确重开条件的诚实零结果，比一个调出来的通过更有说服力。

## 当前未完成项

- ~~所有 arm 统一评分规则~~ · ~~B2 的 `dense_only` 模式~~ · ~~`B3.5` 诊断 arm~~ ·
  ~~统一跨来源证据排序~~ · ~~提高 `max_steps`~~ **——均已完成，上方记录的判定就是
  这些条件下的运行。**
- ▲ **决定结论的 margin 小于它自己的重复间波动。** 本轮已做三遍重复、各自保留独立
  判定，缺口对重复间标准差之比使得"再调一轮系统"无法把改进归因于这次调整。在当前
  题量下增加重复次数解决不了，出路是更多 L2 题目或第二个语料（第三组条件第 5 项）。
- 题集分层不独立：三对旧题 GT 重叠 1.00 / 0.75 / 0.50，所以"L2 与 L3 同时过线"
  弱于两次独立检验。33 题中有 17 题标记 `graph_reverse`，由本语料已索引的调用关系
  反向构造，图解析不了的流程按构造不会出现，这偏向 B4。
- B0 已于 2026-07-31 在**文件级**测得（`results/eval-b0-2026-07-31/`）：它只返回
  路径不返回行号，所以没有 chunk 级结果，也不进入 H1 判定；其数字查询的是活的外部
  索引，无法从已提交字节复现。judge / pairwise 指标仍是 stub。
- migration 已加入 `index_runs` 与 `repos.current_index_run_id`，但 ORM 和
  worker 尚未写入或暴露这条 provenance 记录。
- workbench 缺少 screen-reader live region；TypeScript API contract 仍是手工镜像。
- `dcode.odieyang.com` 尚未解析，production Compose 仅做过本地验证。

复现见 [Operations.md](../en/Operations.md)。
