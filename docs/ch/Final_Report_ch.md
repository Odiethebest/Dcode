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
| `B1` BM25 稀疏检索 | 0.369 | 0.473 | 0.334 | 1.000 |
| `B2` 稠密 RAG | 0.340 | 0.395 | 0.286 | 1.000 |
| `B3` 混合 + 重排 | 0.401 | 0.634 | 0.418 | 1.000 |
| `B4` Dcode（混合 + 调用图 + agent） | 0.448 | 0.763 | 0.494 | 1.000 |

数据来源：`results/eval-h1-l3x12-2026-07-31/` · 裁决写盘于 2026-07-31 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · 合成 gpt-4o-mini

该日期是**已提交的 provenance，而非 harness 输出** —— harness 完全不写时间戳。其观测依据与限制见 `results/eval-h1-l3x12-2026-07-31/provenance.json`。

<!-- END generated: eval-suite-metrics -->

H1 判定：

<!-- BEGIN generated: eval-h1-verdict -->

**结论: `unsupported`**

仅当 B4 在 **L2 与 L3 上同时**比 B2 和 B3 都高出至少 `0.050` composite 分，H1 才算被支持。

| 层级 | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | 是否达标 |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` 跨文件 | 16 | 0.484 | 0.618 | 0.701 | +0.217 | +0.083 | 是 |
| `L3` 架构级 | 12 | 0.411 | 0.463 | 0.508 | +0.097 | +0.045 | 否 |

<!-- END generated: eval-h1-verdict -->

按题目层级的 Recall —— 真正成立的那道阶梯：

<!-- BEGIN generated: eval-level-ladder -->

| 层级 | n | `B1` Recall@5 | `B2` Recall@5 | `B3` Recall@5 | `B4` Recall@5 |
|---|---:|---:|---:|---:|---:|
| `L1` 单跳 | 5 | 0.600 | 1.000 | 1.000 | 1.000 |
| `L2` 跨文件 | 16 | 0.376 | 0.293 | 0.367 | 0.450 |
| `L3` 架构级 | 12 | 0.263 | 0.129 | 0.196 | 0.217 |

<!-- END generated: eval-level-ladder -->

### 如何诚实地读这组数

- **H1 未被支持，在一个层级上差 0.005**。B4 在跨文件题上首次同时越过了对 B2 和
  B3 的 +0.05 门槛，在架构题上以 +0.045 对 +0.050 落空。门槛、题集、指标定义都在
  跑之前定死，之后没动过。差一点仍然是没过；本轮诚实的结论不是"H1 差点通过"，
  而是**在这个精度上 H1 未被解决**。
- **结论对评分口径敏感，换一条口径会翻**。预注册的 `final_verified_evidence_v1`
  让 B2/B3 按检索 top-k 计分、B4 按已验证最终证据计分——两把尺子。harness 同时算了
  B3 自己的最终证据分，所以对称口径是现成的：L2 从 +0.083 变 +0.057（仍过），
  L3 从 +0.045 变 **+0.051（会过）**。**对称口径不予采用，也不是结论。**
  看到一条规则能改变结果之后再去选它，正是预注册要防的事。预注册口径给出
  `unsupported`，那就是结论；另一个口径公布在旁边，因为下一轮必须先为所有 arm
  统一成一条规则。
- **那条不对称的预注册理由被本轮证伪**。criteria set 2 写的是"这刻意让 B4 更难"，
  因为 B4 的证据集通常不足 5 条、命中机会更少。数据相反：B4 的已验证最终证据比它
  自己的候选 top-5 分更高（recall 0.448 对 0.401，MRR 0.763 对 0.634）。精确选证据
  比拥有五个名额更值钱。这条规则**帮了** B4。预测写错了，而且错在对我们有利的方向，
  在此更正而非悄悄删除。
- **调用图自身的贡献很小，且第一次是被量出来而非推断的**。不在 hybrid top-k 里、
  由图或 outline 带来的结构性证据，共产生 **4 个新 GT 命中，分布在 33 题中的 3 题**。
  因此 B4 对 B3 的 margin 不能归因于调用图；两者的差别主要是 agent 的多步证据*选择*，
  而本轮无法把它和图本身分开。能分开的消融（`B3.5`：同一 agent 与 `read_file` 循环，
  关闭调用图与引用工具）尚不存在。
- **修正后的 BM25 保持被测量**。本轮记录了公式、tokenizer、字段、参数和 corpus
  revision。稀疏 `B1` 的 MRR 再次高于稠密 `B2`（0.473 对 0.395），L3 recall 也高于
  其余各 rung——在 33 题上这已不能再用小样本噪声解释，而是这个语料的真实性质。
- **四个 arm 的 groundedness 都在上限，其中两个不是测量值**。`B1` 与 `B2` 用模板作答，
  groundedness 是常量 `1.0`；只有 `B3`/`B4` 走真实校验器。groundedness 占 composite
  四分之一，所以 B2 有四分之一的分是白给的，上表每个 `B4 vs B2` 的 margin 都继承了
  这一点。补 `dense_only` agent 模式是已记录的修法。
- **L3 比以前结实，但仍然脆**。n=12 时一道题最多能拉动该层 0.083，大于它落空的
  0.005。仅 `q-033` 一题 B4 对 B3 就是 −0.156。要让单题权重低于 0.05 的判定 margin
  需要 n > 20。

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
agent 生成路径、把 L3 从 3 扩到 12。当前运行就是这次。

**这次运行显示了什么。** 上一轮诊断出的障碍消失了：B4 被计分的证据不再是 B3 的
检索列表，图终于能够进入指标。B4 在 L2 上过线、在 L3 上差 0.005——同时暴露出三件
此前任何一轮都不可能看见的事：其一，**这条修正自己的理由是错的**，把 B4 按更小的
证据集计分曾被预注册为"让它更难"，实测是优势；其二，**产生 B4 margin 的不是图**，
结构性证据只带来 33 题中 3 题的 4 个新 GT 命中；其三，**结论依赖一条只为一个 arm
预注册过的评分规则**，把同一规则套到 B3 上，L3 就从不过变成过。

## H1 结论

在完整真实模型运行下，**H1 仍未被支持** —— margin 见上方生成的判定表，直接读自
`h1_report.json`。L2 过线，L3 差 0.005。

这个结论不再局限于"被抑制的基线"，也不再局限于"无法度量的比较"：真实 embedding、
真实 reranker、B3/B4 共享的生成路径、以及一条能触及图输出的评分规则都已到位，
B4 依然没有同时过两个层级。改变的还是**原因**——障碍不再是"harness 看不见图"，
而是"图的贡献很小，且现有 margin 部分来自两个 arm 用了不同的评分规则"。

### 第三组重开条件

在下一次运行之前定死，与前两组同样的做法。

1. **▲ 所有 arm 用同一条评分规则**：预注册正式指标究竟是候选 top-k 还是已验证最终
   证据，并对 B2、B3、B4 一视同仁。这是前提，因为当前结论会随这个答案改变。
2. **▲ 为 B2 增加 `dense_only` agent 模式**：否则 B2 根本产不出最终证据，第 1 项
   无法执行，B2 的 groundedness 也会继续是占其 composite 四分之一的常量 `1.0`。
3. **▲ `B3.5` 诊断 arm**：同一 agent 与 `read_file` 循环，关闭调用图与引用工具。
   `B4 − B3` 度量整个 agent 系统，`B4 − B3.5` 才度量调用图本身，也就是真正的假设。
   **仅作诊断，不进入通过标准**——把一个 arm 加进判定规则就是改通过标准。
4. **统一跨来源的证据排序**，`graph_distance` 只记录、不进入排序（可调的图先验就是
   在评测集上拟合超参）。
5. **把 L3 提到 n ≈ 22**，让单题权重低于 0.05 的判定 margin，并且要靠**第二个语料**
   （已索引的 `encode/httpx`）而不是在 Requests 里继续堆题。前置条件是让每道题绑定
   自己的仓库：harness 目前只记录一个 `repo_id_override`、只读一个 `index_revision`。
6. **提高 `max_steps` 或收窄扩张**：B4 会把 8 步预算打满，`get_file_outline` 实际
   触及不到，遍历是被上限截断而不是被规划器结束的。

### 长期承诺

- 门槛、题集、指标定义在跑之前固定，跑完之后不动。
- 当被度量的输出客观上错了，我们改**度量什么**；我们不改通过标准。
- 两种结果都会公布，被证伪的预注册预测同样公布。本轮就证伪了我们自己的一条，已记录在上。
- 当两条都站得住的评分规则给出不同结论时，预注册的那条是结论，另一条公布在旁边。
  事后挑赢的那条这个选项不存在。
- 目标是**真实的判定**，不是通过的判定。一个带着诊断原因和精确重开条件的诚实零结果，比一个调出来的通过更有说服力。

## 当前未完成项

- ▲ 所有 arm 统一评分规则；▲ B2 的 `dense_only` 模式；▲ `B3.5` 诊断 arm。
- 本轮 margin 是单次、含 LLM 合成噪声、且没有重复运行；0.005 的缺口可能小于噪声本身。
- 题集分层不独立：三对旧题 GT 重叠 1.00 / 0.75 / 0.50，所以"L2 与 L3 同时过线"
  弱于两次独立检验。33 题中有 17 题标记 `graph_reverse`，由本语料已索引的调用关系
  反向构造，图解析不了的流程按构造不会出现，这偏向 B4。
- B0 仍需要外部 provider token；judge / pairwise 指标仍是 stub。
- migration 已加入 `index_runs` 与 `repos.current_index_run_id`，但 ORM 和
  worker 尚未写入或暴露这条 provenance 记录。
- workbench 缺少 screen-reader live region；TypeScript API contract 仍是手工镜像。
- `dcode.odieyang.com` 尚未解析，production Compose 仅做过本地验证。

复现见 [Operations.md](../en/Operations.md)。
