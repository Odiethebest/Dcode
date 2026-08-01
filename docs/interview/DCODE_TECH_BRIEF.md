# Dcode 技术底稿

> **这份文档是什么。** 从当前代码重建的一份技术底稿，供求职与技术面试使用。唯一事实来源是**代码本身**（含 migration、配置、脚本、测试、评测产物）；README 与 docs 只作线索，不作结论。每条结论后跟 `path:line`。冲突处以代码为准，冲突另记在文末「文档漂移清单」。
>
> **复验状态。** 全部数值在 2026-07-31 重新执行过：`git rev-parse` / `pytest --collect-only` / `npm test` / `wc -l` / 只读 SQL / 离线重跑 worker 的解析与建边。带 **C** 级标记的数字来自 scratchpad 重算脚本，输入语料 commit `414f0513c33883adf6f2b46901d4f0b38a455851`。
>
> **怎么用。** §4 是数字白名单——**只引用那里出现的数，且必须带上「必须同时说的那句话」那一列**。§5 是面试稿。§1–§3 是支撑材料。

---

## 0. 一分钟定位：这个项目验证了什么

原命题是「**结构感知检索（call graph）优于扁平向量 RAG**」。它的执行判据是一个合取：B4 必须在 L2 与 L3 两层上，同时超过 B2（稠密 RAG）与 B3（hybrid + rerank）各 0.05 个 composite 点。

**判定结果：`unsupported`。**四个比较过了三个——L3 对两个对手都过（+0.247 / +0.169），L2 对 B2 过（+0.136），对 B3 没过（+0.044 < 0.05）。这个结论不撤回、不软化。

**但项目真正验证的东西换了一个。**为了把「调用图的贡献」和「agent 多步取证的贡献」分开，我加了第五个臂 **B3.5**：它是 B4 关掉调用图与引用工具、其余完全相同。差分因此可以分解：

$$
\underbrace{B4 - B3}_{\text{整个 agent 系统}} \;=\; \underbrace{(B4 - B3.5)}_{\text{调用图本身}} \;+\; \underbrace{(B3.5 - B3)}_{\text{多步取证}}
$$

实测（`h1_report.json` → `diagnostics.per_taxonomy`）：

| 层 | 调用图 `B4 − B3.5` | 多步取证 `B3.5 − B3` |
|---|---|---|
| L2 | **+0.0218** | +0.0221 |
| L3 | **+0.0226** | **+0.1466** |

**调用图只值 +0.022；在 L3 上多步取证值它的六倍多。**所以被验证的价值是「**多步取证 + 程序化引用验证**」，不是调用图。

这个区分是我自己造的消融臂测出来的，而**B3.5 在代码层面被硬性排除在判决之外**（`apps/eval/src/dcode_eval/run.py:599-601`、`:605-616`，测试 `apps/eval/tests/test_run.py:686`）——把一个新臂加进判据就是事后改判定规则。所以：**消融否掉了我这个项目的招牌功能，而我没有用它去改判决。**

---

## 1. 现状盘点

### 1.1 分支与最近 10 个 commit

分支 `main`，工作区在开始时干净。

```
0eaa321 Merge pull request #15 from Odiethebest/docs/sync-narrative-to-repeat3
d0a50ed docs: close two claims the audit found unbacked
40d5712 docs(eval): record why the old graph-origin set was invalid, not just imprecise
c37252a fix(frontend): stop hand-typing run figures into the methodology prose
b17621b fix(eval): count the call graph by the same rule the ablation uses
c0b2b7d docs: sync the narrative to the recorded repeat3 run
371e28c Merge pull request #14 from Odiethebest/ziqi_H1_Bm25
864525d eval: measure B0 against the live GitHub index
57c9542 eval: score every arm at file level and make B0 measurable
433c500 docs(env): document GITHUB_TOKEN for the B0 baseline
```

`b17621b` 已用 `git rev-parse` 核对（`b17621b77adf9175555c9a51ff251e41f265c6e1`）。最近 10 个里 6 个是**评测协议与文档口径的修正**，不是功能开发——项目已进入"让数字和叙述对齐"的阶段。

### 1.2 服务、包与入口

| 服务 | 类型 | 入口 | 容器命令 | 端口 |
|---|---|---|---|---|
| `api` | FastAPI 网关 | `apps/api/src/dcode_api/main.py:31` | `infra/docker/api.Dockerfile:26-28` | 8000 |
| `agent` | FastAPI + LangGraph | `apps/agent/src/dcode_agent/main.py:46` | `infra/docker/agent.Dockerfile:25-27` | 8001 |
| `worker` | RabbitMQ 消费者（无 HTTP） | `apps/worker/src/dcode_worker/main.py:33` | `infra/docker/worker.Dockerfile:23` | — |
| `embedding` | 自托管 sidecar | `apps/embedding/src/dcode_embedding/main.py:56` | `infra/docker/embedding.Dockerfile:29` | 8002 |
| `reranker` | 自托管 sidecar | `apps/reranker/src/dcode_reranker/main.py:53` | `infra/docker/reranker.Dockerfile:28` | 8003 |
| `frontend` | React SPA → nginx | `apps/frontend/src/main.tsx` | `infra/docker/frontend.Dockerfile:23` | 5173→80 |
| `eval` | 离线 CLI，不是服务 | `apps/eval/src/dcode_eval/run.py`（`apps/eval/pyproject.toml:8-9`） | — | — |
| `packages/shared` | 库，无入口 | `packages/shared/src/dcode_shared/` | — | — |

uv workspace 7 个成员：`pyproject.toml:8-16`。

`embedding` / `reranker` 在 compose 里挂 profile（`docker-compose.yml:132-133`、`:153-154`），**`make up` 不会启动它们**——这是必须先 `make embedding-host` / `make reranker-host` 的机制性原因。

### 1.3 启动方式与检查链

```bash
make embedding-host   # :8002，等 "Embedding model ready"
make reranker-host    # :8003，等 "Reranker model ready"
make up               # 核心栈
make check            # lint + typecheck + test（Makefile:80）
```

`make lint`（`Makefile:65-70`）除 ruff / eslint 外还跑 `python3 scripts/sync_eval_artifacts.py --check`——**评测数字漂移会让 lint 失败**。这是不常见但值得讲的设计：每个展示出来的评测数字有且只有一个来源（`results/`），其余全部生成。

### 1.4 外部依赖与真实配置落点

版本来自 `uv.lock`（锁定值，不是 pyproject 的下限）：fastapi 0.136.3 · langgraph 1.2.4（唯一 import 点 `apps/agent/src/dcode_agent/graph.py:13`）· openai 2.49.0 · sentence-transformers 4.1.0 · torch 2.12.1（CPU wheel index）· sqlalchemy 2.0.50 · asyncpg 0.31.0 · pgvector 0.4.2 · redis 8.0.0 · aio-pika 9.6.2 · alembic 1.18.4。

| 组件 | 代码默认 | 生效值 | 证据 |
|---|---|---|---|
| Embedding 模型 | `stub` | `jinaai/jina-embeddings-v2-base-code` | `packages/shared/src/dcode_shared/settings.py:45`；`provenance.json` → `models.embedding` |
| Embedding 维度 | `1024` | **`768`** | `settings.py:46`；`docker-compose.yml:60`；`provenance.json` → `corpus.embedding_dimensions` |
| Reranker | `stub` | `BAAI/bge-reranker-v2-m3` | `settings.py:55`；`provenance.json` → `models.reranker` |
| LLM 合成 | `stub` | `gpt-4o-mini` | `apps/agent/src/dcode_agent/settings.py:21`；`provenance.json` → `models.synthesis` |
| LLM judge | `stub` | **`stub`（未接）** | `settings.py:59`；`provenance.json` → `models.judge` |
| 队列名 | `dcode.index_jobs` | 同 | `apps/api/src/dcode_api/settings.py:11` 与 `apps/worker/src/dcode_worker/settings.py:10`**各定义一份** |

`.env` 不入库（`.gitignore:11`），`.env.example` 里全是 `stub`。**"真实模型路径"是本机 `.env` 的事实，不是仓库默认**——面试时这句要说清。

### 1.5 测试：数量与它们真正断言的行为

**pytest 291 个用例**（`uv run pytest --collect-only` 实测，32 个文件）。**vitest 73 个 / 16 个文件，全绿实跑**（1.14s）。

代码量：Python 源码 **10,952** 行 / Python 测试 **7,678** 行；前端 `src` **4,746** 行 / 前端测试 **1,445** 行。（Python 计数排除了 `apps/frontend/node_modules` 下 16 个共 1743 行的 `.py`；不排除会虚增到 12,695。）

按"它们钉住什么"归类：

| 断言的行为 | 代表用例 |
|---|---|
| **诚实性契约**（最密集） | 无引用答案零分 `apps/agent/tests/test_uncited_answers.py:39,64,130`；未验证引用被抹除且中文本地化 `test_groundedness.py:379,411,452`；前端"streaming 时不给分、不给 chip" `apps/frontend/tests/Turn.test.tsx` |
| **评测协议不可被悄悄改** | 每个 agent arm 同一条计分规则 `apps/eval/tests/test_run.py:606`；B3.5 只做 diagnostic `:686`；groundedness 不再左右 H1 `:755`；语料中途变了拒跑 `:518` |
| **调用图解析的精度取舍** | 继承链 `self.x()` `apps/worker/tests/test_graph_stage.py:309`；自有方法优先 `:340`；局部构造对象 `:372`；重新赋值的局部变量**不给类型** `:401`；环形继承不卡死 `:438` |
| **BM25 是真 BM25** | idf 用语料 df `packages/shared/tests/test_bm25.py:25`；tf 饱和 `:34`；长文归一 `:42`；公式与声明一致 `:49` |
| **加权 RRF 的方向** | 加权时 dense 胜出 `apps/api/tests/test_internal_routes.py:444`；等权时 sparse 噪声仍有竞争力 `:465` |
| **降级不抛异常** | reranker 挂了退回融合序 `test_internal_routes.py:528`；embedding stub 退纯 sparse `:552`；工具失败进合成 `apps/agent/tests/test_graph.py:776`；排序失败退观察序 `:1274` |
| **API 幂等与缓存边界** | 重复提交复用 `apps/api/tests/test_repos_route.py:107,135`；history 参与缓存键 `test_query_route.py:137`；错误流不入缓存 `:117` |
| **前后端 schema 不漂移** | `apps/frontend/tests/types.test.ts`（编译期镜像检查） |

### 1.6 评测产物

`results/` 下 14 个目录 + 2 个 md。**当前唯一结论目录**是 `results/eval-h1-repeat3-2026-07-31/`（88 个入库文件，最后一次提交 `2026-07-31 15:17:48 -0700`，commit `19289c5`）。

- `run_config.json` — 5 个 arm、k=5、repeats=3、`scoring_protocol: uniform_final_verified_evidence_v2`、三项 composite、BM25 参数
- `h1_report.json` — `decision: unsupported`，阈值 0.05；`comparisons` 四个 margin；`four_term` 旧口径；`per_repeat` 三次独立判定
- `suite_summary.json` — 33 题，每 arm 的 recall/mrr/ndcg + candidate/final 两套 + groundedness（全 1.0）+ `pairwise_win_rate: null`
- `provenance.json` — 手写产物（**非 harness 输出**，证据见附录 B 末）；语料 `psf/requests` @ `414f051`，726 chunks / 473 edges / 768 维；**12 条 limitations**
- `B1/ B2/ B3/ B3.5/ B4/` 各三份产物；`repeat-1/2/3/` 各自完整一份

题集：`apps/eval/src/dcode_eval/questions/data/questions.jsonl`，33 行，sha256 `db813124…a28b45`（与 `provenance.json` 记录一致）。分布 `L1:5 / L2:16 / L3:12`；来源 `manual:16 / graph_reverse:17`。

`results/eval-b0-2026-07-31/`：B0 = 外部 GitHub code search，33 题，**只有 file-level**，`provenance.json` 明说不可复现。

> ⚠️ 目录里的 `B1 2/`、`repeat-1 2/` 是 iCloud 同步副本，**未入 git**，不是产物。

**本节小结**：这一层解决的是"任何人接手都能在十分钟内知道有哪些进程、它们怎么起来、真实模型配在哪、哪个评测目录才算数"。

---

## 2. 逻辑结构

### 2.1 索引链路

**三句话。** 网关校验 Git URL、查是否已索引过、落一行 `repos`，把 `{repo_id, url}` 发进 RabbitMQ 持久化队列后立刻返回 202——用户等的是入队不是索引。worker 单并发消费，跑一条严格单调的六态状态机：clone → parse → chunk → embed → graph，每完成一步同时写两处（Postgres 的 `repos` 行是持久真相，Redis 的 `job:{repo_id}` 是给轮询的细粒度快照）。任一步抛异常，状态机停在那一步并标 `failed`，但 `handle_job` 保证不向 RabbitMQ 抛出——否则消息会被无限重投。

| # | 模块 → 函数 | `file:line` | 跨边界 |
|---|---|---|---|
| 1 | 前端 `submitRepo` | `apps/frontend/src/api/client.ts:28-38` | **HTTP** POST `/api/v1/repos` |
| 2 | api `submit_repo` | `apps/api/src/dcode_api/routes/repos.py:39-92` | |
| 2a | URL 白名单 | `repos.py:187-200` / `:203-224` | 拒 localhost、私有/环回/链路本地 IP（SSRF 面） |
| 2b | 幂等 | `repos.py:126-151` / `:107-123` | **SQL** `WHERE url IN (variants) AND status IN (6 种可复用态)` |
| 2c | 落库 + commit | `repos.py:73-76` | **SQL**，**先 commit 再发消息**，否则 worker 读不到行 |
| 3 | `publish_index_job` | `apps/api/src/dcode_api/deps.py:44-58` | **AMQP** `dcode.index_jobs`，`DeliveryMode.PERSISTENT`（`:55`） |
| 3a | 发布失败补偿 | `repos.py:80-90` | 行已持久 → 标 `failed` + 503，不留"永远 queued" |
| 4 | worker `consume_loop` | `apps/worker/src/dcode_worker/main.py:19-30` | **AMQP** `prefetch_count=1`（`:23`）、`durable=True`（`:24`） |
| 5 | `handle_job` | `apps/worker/src/dcode_worker/pipeline.py:59-168` | 阶段表 `:51-56` |
| 5a | 每阶段双写 | `pipeline.py:239-262` | **SQL**（`:265-282`）+ **Redis**（`:285-304`，Redis 异常吞掉不影响索引） |
| 6 | clone | `stages/clone.py:14-27` | **子进程** `git clone --depth=1`，超时 180s（`:11`） |
| 7 | parse | `stages/parse.py:27-76` | 跳过目录 `:13-24`；>1MB `:43-47`；解码/语法错误 `:50-62` |
| 8 | chunk | `stages/chunk.py:12-23` | 纯内存 AST 切分 |
| 9 | embed | `stages/embed.py:38-69` | **HTTP** → `:8002`；Redis 内容寻址缓存（`cache.py:13-16`） |
| 9a | 写 chunks + 递增 revision | `embed.py:173-179` | **SQL**，**同事务** `DELETE chunks` + `index_revision + 1` |
| 10 | graph | `stages/graph.py:55-139` | **SQL** 先删 edges/symbols（`:130-131`），`flush` 拿 id 后插 edges（`:133-134`） |
| 11 | ready | `pipeline.py:135-146` | progress=100 |
| 12 | 前端轮询 | `client.ts:40-46` → `repos.py:158-184` | Redis 覆盖 DB（`:175-183`） |

"严格单调"落在数据结构上：阶段顺序是不可变元组 `DEFAULT_STAGES`（`pipeline.py:51-56`），每项带 `(status, name, runners, in_progress%, done%)`。没有跳转表、没有条件分支。

### 2.2 `chunks.tsv` 从未写入，对检索路径的实际影响

**事实链**：列建在 `infra/migrations/versions/001_initial_schema.py:92`，GIN 索引建在 `:101`，ORM 声明在 `packages/shared/src/dcode_shared/db/models.py:129`。**全仓 grep `tsv` 只命中这三处 + 一条注释**；`embed.py:180-196` 构造 `DBChunk` 时列出 10 个字段，**没有 `tsv`**；无触发器、无 generated column、`infra/postgres/init.sql` 也没有。

```
                       ┌─────────────────────────────────────────────┐
                       │ Postgres: chunks                            │
   ┌───────────────────┤  embedding vector(768)  ─── HNSW cosine ────┼──┐
   │                   │  tsv TSVECTOR (NULL)    ┄┄┄ GIN ┄┄┄┄┄┄┄┄┄┄┄┄┼┄┄┼┄ 死路
   │                   │  content / symbol_name / file_path / sig    │  │
   │                   └──────────────┬──────────────────────────────┘  │
   │                                  │ SELECT（load_only 8 列，无 embedding/tsv）
   │                                  │ retrieval/bm25.py:66-82
   │                                  ▼
   │                    _load_corpus → BM25Index（进程内 LRU，8 个 repo）
   │                                  │ retrieval/bm25.py:55-114
   │                                  ▼
   │                    search_repo_bm25  ← sparse 侧真正跑的函数
   │                                  │ retrieval/bm25.py:28-52
   │                                  ▼
   │                    _search_sparse_candidates  internal.py:314-331
   │                                  │
   │  _search_dense_candidates        │
   └─ internal.py:334-358 ────────────┤
      （pgvector cosine_distance）     │
                                      ▼
                    ┌──────────────────────────────────┐
                    │ _fuse_search_candidates          │  ← 融合点
                    │ 调用处 internal.py:297           │
                    │ 加法   internal.py:493-496       │
                    └──────────────┬───────────────────┘
                                   ▼
                    _rerank_candidates  internal.py:408-457
                                   ▼
                    _take（后置过滤 tests）internal.py:302-311
```

sparse 侧完整调用链：`internal.py:289` → `search_repo_bm25`（`apps/api/src/dcode_api/retrieval/bm25.py:28-52`）→ `_load_corpus`（`:55-114`，SQL 在 `:66-82`，建索引在 `:86-96`）→ `BM25Index.scores`（`packages/shared/src/dcode_shared/bm25.py:92-123`）→ `score > 0` 过滤 + `(-score, file_path, start_line, id)` 稳定排序（`retrieval/bm25.py:43-51`）。

**三个实际后果**：① 稀疏检索是应用层的，每个 `(repo_id, index_revision)` 首查要把全仓 chunk 拉进进程建索引，LRU 只有 8 个 repo（`retrieval/bm25.py:16`）——**明确的规模上限，不是隐藏 bug**；② `index_revision` 承担全部缓存失效责任（键在 `:60`，递增在 `embed.py:177-179`）；③ GIN 索引在生产库里是纯开销——每次 INSERT 维护一个永远为 NULL 的索引。

### 2.3 查询链路

**三句话。** 前端把「问题 + 已完成轮次的历史」POST 到网关，网关先裁剪历史、算缓存键，命中就**逐字节重放**上次的整条 SSE 流，否则转发给 agent 并**边转发边缓冲**（只有不含 `error` 的流才写回缓存）。agent 收到后**不在响应协程里跑图**——先返回一个绑定到 `asyncio.Queue` 的 SSE 响应，把 LangGraph 扔进后台 task，节点边跑边推事件。图跑完后主流程才补发所有 `citation` 和唯一的 `final_answer`，然后关流。

| # | 模块 → 函数 | `file:line` | 跨边界 |
|---|---|---|---|
| 1 | `useThread.submit` | `apps/frontend/src/hooks/useThread.ts:106-139` | `AbortController`（`:114`）、`buildHistory`（`:43-55`） |
| 2 | `streamQuery` | `apps/frontend/src/api/client.ts:79-130` | **HTTP POST + SSE**；手写解析，按 `\n\n` 切（`:109`） |
| 3 | api `_stream_query` | `apps/api/src/dcode_api/routes/query.py:49-73` | |
| 3a | 历史截断 | `query.py:112-142` | 6 轮 / 2000 总字符 / 4000 单轮（`api/settings.py:15-17`），**从新到旧保留** |
| 3b | 缓存键 | `packages/shared/src/dcode_shared/cache.py:24-52` | 空 history 时与旧键**逐字节相同**（`:39-41`） |
| 3c | 命中 → 整流重放 | `query.py:62-65` | |
| 3d | 转发 | `query.py:76-109` | **HTTP** → `agent:8001/internal/query`，带内部密钥头（`deps.py:70`） |
| 3e | 只缓存无 error 的流 | `query.py:72-73` | |
| 4 | agent `internal_query` | `apps/agent/src/dcode_agent/main.py:80-109` | 鉴权 `:86`；`InternalQueryRequest.mode` `:53-61` ← **四个评测臂的唯一开关** |
| 4a | **后台 task** | `main.py:94-104` | 响应体是 `emitter.iter_bytes()`（`:106`） |
| 5 | `compiled_graph.ainvoke` | `main.py:124` | runtime 注入 emitter/registry/redis/db/llm（`:130-136`） |
| 6 | LangGraph 拓扑 | `apps/agent/src/dcode_agent/graph.py:767-795` | |
| 7 | 补发 citations + final_answer | `main.py:142-161` | |

```
START ──► contextualize ──► plan ──┬──(decide_after_plan)──► tool_call ──┬──► plan   (循环)
                                    │                                      │
                                    └──────────────────────────────────────┴──► synthesize
                                                                                    │
                                                                          groundedness_check ──► END
```

| 节点 | 定义 | 做什么 | 发什么 SSE |
|---|---|---|---|
| `contextualize` | `graph.py:29-69` | 有 history 才跑。LLM 改写成独立问句（`:46`），再对"纯代词的调用类追问"做确定性兜底绑定（`:59-63`）。原句存进 `raw_query`（`:66`）——**答案语言按原句判定** | 改写生效时 1 个 `thought`（`:68`） |
| `plan` | `graph.py:72-90` | **规则式**规划器，`_select_next_tool`（`:798-812`） | 选中工具时 1 个 `thought`（`:89`） |
| `tool_call` | `graph.py:93-172` | 校验参数 → 缓存键 → 查缓存 → 执行 → 写缓存 → 记 observation → `step_count += 1` | `tool_call`（`:122`）+ `tool_result`（`:169` 或 `:206`） |
| `synthesize` | `graph.py:212-250` | 先算模板答案（`:221`），有 LLM 且有 observation 就换流式 LLM（`:225-231`） | LLM 路径 1 个 `thought`（`:263`）+ N 个 `partial_answer`（`:274`）；模板路径 **1 个**整段（`:249`） |
| `groundedness_check` | `graph.py:708-741` | `verify` → `enforce_groundedness` → 只留已验证引用 | **不发任何事件** |

**11 个工具**（注册表 `apps/agent/src/dcode_agent/tools/__init__.py:22-39`）。全部经 `common.fetch_internal_json`（`tools/common.py:12-35`）走 HTTP GET 到 `/internal/*`，**除了** `read_file` / `grep` / `list_directory` 走本地文件系统（worker 与 agent 共享 `repo_workdirs` volume，`docker-compose.yml:104` 与 `:186`）。

| 工具 | Args | Result | 边界 |
|---|---|---|---|
| `search_code` | `{query:str≥1, k:int∈[1,50]=10, mode:"hybrid"\|"dense"\|"sparse"}` `search_code.py:23-26` | `{chunks:list[Chunk]}` | HTTP |
| `read_file` | `{path:str, line_range:(int,int)}` + 校验器 `read_file.py:13-24` | `{path,line_range,content}` | **FS**，穿越拦截 `common.py:70-76` |
| `find_definition` / `find_references` | `{symbol:str}` | `{locations}` | HTTP |
| `find_call_path` | `{start,end,max_depth:int∈[1,6]=4}` `find_call_path.py:22-25` | `CallPath` `schemas.py:211-232` | HTTP |
| `get_call_neighbors` | `{symbol:str≥1, direction:"callers"\|"callees"\|"both"}` `get_call_neighbors.py:15-17` | `CallNeighbors` `schemas.py:193-208` | HTTP |
| `get_dependencies` / `get_dependents` | `{module:str}` | `{locations}` | HTTP |
| `get_file_outline` | `{path:str}` | `{path, locations}` | HTTP |
| `grep` | `{pattern:str}` `grep.py:22-23` | `{locations}` | **子进程/FS**，无 rg 时回退纯 Python |
| `list_directory` | `{path:str="."}` | `{entries:[{name,kind}]}` | **FS** |

**工具缓存键** `tool:{tool}:{repo_id}:{sha256(canonical_json(args))[:16]}`（`cache.py:19-21`），TTL 24h。`search_code` 的 `mode` 是**参数不是环境状态**，因为它必须进缓存键——否则 B2 的 dense 检索与 B3 的 hybrid 检索会撞同一条目（`search_code.py:8-11`）。

### 2.4 终止条件与降级路径

**步数上限 `max_steps = 14`**（`apps/agent/src/dcode_agent/settings.py:14`，注释 `:9-13` 记录从 8 提上来的原因）。`step_count` 在成功（`graph.py:168`）与失败（`:189`）两处都递增——**失败也计步**。

除步数外的全部提前退出：

| # | 位置 | 条件 | 去向 |
|---|---|---|---|
| 1 | `plan_node` `graph.py:74-77` | `step_count >= 14` | 清 pending → 分支 5 |
| 2 | `plan_node` `graph.py:79-83` | `_select_next_tool` 返回 `None` | 清 pending → 分支 5 |
| 3 | `decide_after_plan` `graph.py:751-752` | `state.error is not None` | synthesize |
| 4 | `decide_after_plan` `graph.py:753-754` | `step_count >= 14` | synthesize |
| 5 | `decide_after_plan` `graph.py:757-758` | `pending_tool_name is None` | synthesize |
| 6 | `decide_after_plan` `graph.py:755-756` | `draft_answer is not None` | **当前拓扑下不可达**（`draft_answer` 只在 `:239` 赋值，而 `synthesize → groundedness_check → END`） |
| 7 | tool_call 出边 `graph.py:789` | `state.error is not None` | synthesize；否则回 plan |

`_select_next_tool` 返回 `None` 的来源：`graph.py:810-811`（`expansion == "none"`，即 **B3/B2 恰好 1 次工具调用**）· `:911-913`（专用路由已调过同参）· `:915-916`（`_needs_multihop` 为假）· `:918-920`（无 seed chunk）· `:977`（候选用尽）· `:1009/:1021/:1040`（调用类问题的三条收敛点）。

**expansion 策略表**在 `apps/agent/src/dcode_agent/state.py:32-44`——四个 mode 到 `(检索模式, 扩展策略)` 的唯一映射。`agent_no_graph`（B3.5）与 `full`（B4）只差 `allow_structural = expansion == "full"`（`graph.py:897`），被禁集合是 `STRUCTURAL_TOOLS = GRAPH_TOOLS`（`state.py:57` → `packages/shared/src/dcode_shared/graph_tools.py:58-67`）。

**异常降级路径**：

| 节点 / 位置 | 来源 | 捕获点 | 结果 |
|---|---|---|---|
| `contextualize` | LLM 改写失败 | `graph.py:47-53` | 记日志，**继续用原问句**，查询不降级 |
| `plan` | `_select_next_tool` 抛出 | **无捕获** | 冒泡 → `main.py:162-163` → `error` 事件 |
| `tool_call` | 参数校验失败 | `graph.py:114-117` | `_record_tool_failure`（`:175-209`）→ 转 synthesize |
| `tool_call` | 执行/缓存解码失败 | `graph.py:138-139` | 同上 |
| `tool_call` | registry 缺失 / 未知工具 | `:105`、`:110` 主动 raise | 冒泡 → `error` |
| `tool_call` | **Redis 读写失败** | **无捕获**——`_cache_get`（`:130`）与 `_cache_set`（`:142`）都在 `try`（`:132-139`）之外 | 冒泡 → `error`。⚠️ 全仓唯一没兜 Redis 的地方（worker `pipeline.py:303` 兜了，网关 `query.py:148,159` 兜了） |
| `synthesize` | LLM 流式失败 | `graph.py:275-282` | 返回 `None` → **退回模板合成** |
| `synthesize` | 证据 hydration 失败 | `graph.py:519-521` | 该证据留空文本，继续 |
| `synthesize` | reranker 失败 | `graph.py:471-472` | **退回 observation 顺序** |
| `synthesize` | `create_reranker_client` 配置错误 | **无捕获**（`reranker.py:124`；调用链 `graph.py:259 → :466 → :539` 都在 `:265` 的 try 之外） | 冒泡 → `error`，误配置在查询时才暴露 |
| `groundedness_check` | DB 失败 | **无捕获** | 冒泡 → `error`。**答案已流完但无 `final_answer`** → 前端判 `interrupted` |
| 全局兜底 | 任何 | `main.py:162-163` | `error{code:"INTERNAL"}`，`finally` 关流（`:164-165`） |
| agent 不可达 | httpx `RequestError` | `query.py:96-109` | 网关自发 1 个标注 `(skeleton)` 的 `thought` + 1 个 `error` |

**一句话**：工具层失败是**降级**（仍给答案，头部加故障提示 `graph.py:699-705`），基础设施层失败是**终止**（发 error，不给答案）。分界画在 `_record_tool_failure` 上。

### 2.5 SSE 事件序列

七种，闭集（`packages/shared/src/dcode_shared/events.py:13-21`）。

| 事件 | payload | 类型定义 | 发出处 |
|---|---|---|---|
| `thought` | `step:int, content:str` | `events.py:24-26` | `graph.py:1386-1390` |
| `tool_call` | `step:int, tool:str, args:dict` | `events.py:29-32` | `graph.py:1393-1397`（`:122`） |
| `tool_result` | `step:int, tool:str, result_summary:str` | `events.py:35-38` | `graph.py:1400-1404`（`:169`/`:206`），摘要 `:1437-1473` |
| `partial_answer` | `delta:str` | `events.py:51-52` | `graph.py:1407-1411`（`:274`/`:249`） |
| `citation` | `symbol, file_path, line, verified, chunk_id?, evidence_id?, origins[]` | `events.py:41-48` | `main.py:142-151` |
| `final_answer` | `answer, citations[], groundedness` | `events.py:55-58` | `main.py:157-161` |
| `error` | `code, message` | `events.py:61-63` | `main.py:163`；网关 `query.py:86-92`、`:106-109` |

线格式 `sse_encode`（`events.py:66-69`）→ `event: {name}\ndata: {json}\n\n`，**纯 LF**；前端按 `/\n\n/` 切（`client.ts:109`），两边对得上。

```
[ thought ]                     ← contextualize，仅当有 history 且改写生效
( thought → tool_call → tool_result )*   ← ReAct 循环，0..14 次
[ thought ]                     ← 合成，仅 LLM 路径
partial_answer+                 ← LLM N 个；模板恰好 1 个
citation*                       ← 图跑完后一次性补发
final_answer                    ← 恰好 1 个
```

三条**代码保证的**不变量：① `citation` 一定在所有 `partial_answer` 之后、`final_answer` 之前——它们不在图里发，而在 `ainvoke` 返回后才发（`main.py:124` → `:142`，注释 `:153-155`）；② 同一 step 的 `tool_call` 与 `tool_result` 编号一致（`:1397` 用 `step_count+1`，`:1404` 在 `:168` 递增后用 `step_count`）；③ **发出的 `citation` 全部 `verified=true`**，因为 `state.citations` 被覆盖为 `enforced.citations`（`graph.py:727-738`；`groundedness.py:377,401`）——⚠️ 前端的 amber「未验证」chip **在实时流里到不了**。

| | `done` | `interrupted` |
|---|---|---|
| 判定 | 收到 `final_answer` | 流关闭且从未收到 |
| 代码 | `apps/frontend/src/hooks/useThread.ts:32` | `useThread.ts:33` |
| **不会发出** | — | **`final_answer` 永不出现**；`citation` 通常也不出现 |
| 渲染 | `AnswerMarkdown` + 绑定 citations | `InterruptedDraft`（`Turn.tsx:112-137`），标题 "Draft · never verified" |
| 引用 chip | 绑定（`Turn.tsx:40`） | **一律不绑定**，退化为惰性 `CodeChip` |
| Sources 页脚 | 有（`Turn.tsx:41`） | 无 |
| 药丸 | 绿底 + 分数（`Trace.tsx:75-82`） | 中性灰 + "interrupted"（`:95-99`），**静态不脉动**（注释 `:92-94`） |
| 区分停止/断线 | — | `turn.stopped`（`useThread.ts:99-101`），文案 `Turn.tsx:130` |

`Turn.tsx:33-39` 点明为什么必须分开：**citation 在 `final_answer` 前一瞬刷出，所以被打断的 turn 可能已握有若干条逐条已验证的 citation，而正文从未经过抹除**——绑定它们等于给没挣到保证的散文盖章。

**前端消费点**：切分 `client.ts:105-122` · 单块解析 `:132-160` · 事件名→判别联合 `:162-179` · 尾部 buffer 兜底 `:124-129` · 事件入 turn `useThread.ts:122` · 状态判定 `:30-34` · Trace 过滤集 `Trace.tsx:7`、渲染 `:26-52`、args 摘要 `:19-24` · `partial_answer` 拼接 `Turn.tsx:22-25` · `final_answer` `Turn.tsx:19-21,30` · groundedness 药丸 `Trace.tsx:58,75-82` · citation 合并 `Turn.tsx:31` → `lib/citations.ts:13-25` · Sources `Turn.tsx:41` → `citations.ts:52-59` · `error` `Turn.tsx:26-28,62-66` · 多轮回填 `useThread.ts:43-55`（**只取有 `final_answer` 的 turn**）。

### 2.6 Groundedness 数据流

**先修正一个常见误解：`judge` 是 stub 与 `suite_summary.json` 里的 `1.0` 无关。** `judge_model` 在全仓被读取零次（只有 `packages/shared/src/dcode_shared/settings.py:59` 的定义）；`StubJudge`（`apps/eval/src/dcode_eval/metrics/judge.py:39-46`）从未被实例化。judge 为 stub 的唯一后果是 `pairwise_win_rate` 硬编码为 `None`（`run.py:459`、`:418`）。

那个 `1.0` 有**两种来源**：

**(a) B1 —— 硬编码常量。**
```
suite_summary.json "groundedness": 1.0
  ← run.py:450  average("groundedness")
  ← run.py:137  answer.groundedness
  ← baselines/bm25.py:18  common.template_answer(...)
  ← ★ apps/eval/src/dcode_eval/baselines/common.py:37   groundedness=1.0   ← 字面量
```
（同函数 `:29` 在无检索结果时返回 `0.0`；默认值另在 `baselines/base.py:23`。）

**(b) B2/B3/B3.5/B4 —— 实测值，恰好等于 1.0。**
```
  ← ★ apps/eval/src/dcode_eval/baselines/common.py:75   float(payload["groundedness"])
  ←（SSE 边界）
  ← apps/agent/src/dcode_agent/main.py:160    state_dict["groundedness_score"]
  ← apps/agent/src/dcode_agent/graph.py:739   enforced.score
  ← apps/agent/src/dcode_agent/groundedness.py:403  score=result.score
  ← apps/agent/src/dcode_agent/groundedness.py:218  verified_count / len(checks)
```

**在决策链路中被排除的实现位置**，三处缺一不可：`_COMPOSITE_TERMS = ("recall_at_k","mrr","ndcg_at_k")`（`run.py:666`）→ `_composite_score`（`:669-670`）→ `_h1_report` 用它算三个分数与 margin（`:554-560`、`:588`）。groundedness 唯一进入报告的地方是 `_legacy_four_term_composite`（`:673-680`），写进 `comparisons[tax]["four_term"]`（`:571-584`），**永不参与 `decision`**。

⚠️ `answers_without_citations`（`run.py:458`）与 groundedness 是**成对的**：「一条引用都没有」和「每条引用都失败」在这个约定下都算 0.0，均值分不开（论证在 `:451-457`）。当前 run 五个 arm 该值都是 0，所以 1.000 确实是"引用了并且全对"。

### 2.7 数据模型

| 表 | 关键列 | 定义位置 |
|---|---|---|
| **repos** | `id UUID PK`；`url`；`commit_sha`；`status ENUM(7)`；`progress`；`error`；`index_revision NOT NULL default 0`；`created_at/updated_at`；`current_index_run_id → index_runs.id` | `db/models.py:79-102`；migration `001:32-66` + `002_bm25:20-23` + `002_index_runs:91-98` |
| **chunks** | `repo_id → repos.id CASCADE`；`file_path`；`chunk_type ENUM(4)`；`parent_symbol`；`symbol_name`；`signature`；`start_line/end_line`；`imports JSONB`；`content`；**`embedding Vector(768)`**；**`tsv TSVECTOR`（永远 NULL）** | `db/models.py:110-132`；migration `001:69-93` |
| **symbols** | `repo_id CASCADE`；`qualified_name`；`kind ENUM(4)`；`file_path`；`line`；`chunk_id → chunks.id SET NULL` | `db/models.py:140-159`；migration `001:104-126` |
| **edges** | `repo_id CASCADE`；`source_id/target_id → symbols.id CASCADE`；`edge_type ENUM(4)`；`source_line` | `db/models.py:167-187`；migration `001:135-162` |
| **index_runs** | 15 列；`repo_id → repos.id **RESTRICT**`；**BEFORE UPDATE OR DELETE 触发器拒绝任何变更** | migration `002_index_runs:60-89`、`003:47-51`。**代码里没人写它** |

索引：`ix_chunks_repo_file`（`001:94`）· `ix_chunks_embedding_hnsw USING hnsw (embedding vector_cosine_ops)`（`:97-100`）· `ix_chunks_tsv_gin`（`:101`，**无人使用**）· `ix_symbols_repo_qname_unique UNIQUE`（`:127-132`）· `ix_edges_source`（`:163`）· `ix_edges_target`（`:164`，反向边索引，`internal.py:895` 点名）。

**向量维度绑定时刻**：`Vector(shared_settings.embedding_dim)` 出现在 ORM（`db/models.py:128`）与 **migration（`001:91`）**，后者是 `alembic upgrade` 执行那一刻的环境值被固化进 DDL。**改维度必须重建库。**

缓存键空间：`embed:{model}:{sha256(text)}`（永久，`cache.py:13-16`）· `tool:{tool}:{repo}:{hash}`（24h，`:19-21`）· `query:{repo}:{sha256(history\x1f query)[:32]}`（1h，`:24-52`）· `job:{repo}`（完成后 7 天，`:55-57`）。`\x1f` 作分隔符因为它不可能出现在 JSON 里（`:50`）。

### 2.8 模块依赖方向

```
                    ┌──────────────────┐
                    │  dcode_shared    │  schemas · events · cache · db.models
                    └────────▲─────────┘  settings · bm25 · symbols · graph_tools
                             │            embedding · reranker · testpaths · internal
        ┌──────────┬─────────┴────────┬──────────┐
   dcode_api   dcode_worker      dcode_agent  dcode_eval
```

实测（`grep -rl "^from <pkg>\|^import <pkg>"`）：**无反向依赖、无循环**。四个应用包互相**零 Python import**，只通过 HTTP / AMQP / Postgres / Redis / 共享 volume 通信。

`dcode_eval` 尤其干净：`apps/eval/pyproject.toml:6-9` 只依赖 `httpx` 和 `dcode-shared`——**评测 harness 结构上无法 import 被测系统**，只能像外部客户端一样打它的 HTTP 口。这是"评测不会因共享内存状态而作弊"的结构性保证。

两处**跨包重复定义**（非循环，但是漂移风险）：队列名 `dcode.index_jobs` 在 `api/settings.py:11` 与 `worker/settings.py:10` 各写一份；`apps/frontend/src/api/types.ts` 是 `dcode_shared.schemas` 的手抄镜像，靠 `apps/frontend/tests/types.test.ts` 做编译期钉子。

**本节小结**：逻辑结构解决的是"五个进程各自只知道自己该知道的事"——共享的是**类型定义**（一个包），共享的**不是**运行时状态。

---

## 3. 核心算法

每项按固定顺序：**直觉 → 数学 → 代码对应 → 关键参数与位置 → 复杂度 → 失败模式与兜底**。

### 3.1 代码分块策略

**直觉。** 不按固定字符数切，而是**按 Python 自己的语法结构切**：一个函数一块、一个方法一块、一个类一块、模块 docstring 一块。好处是每块都有名字、签名、行号——命中之后可以直接说"在 `auth.py:85` 的 `HTTPBasicAuth`"，而不是"在第 37 段"。

**数学。** 设文件 $f$ 的 AST 为 $T_f$，顶层语句序列 $B_f = T_f.\mathrm{body}$：

$$
C_f = \underbrace{M_f}_{\text{module doc}} \cup \!\!\bigcup_{\substack{c \in B_f \\ c \in \mathrm{ClassDef}}}\!\!\Big(\{c\} \cup \{m \in c.\mathrm{body} : m \in \mathrm{FuncDef}\}\Big) \cup \!\!\bigcup_{\substack{g \in B_f \\ g \in \mathrm{FuncDef}}}\!\!\{g\}
$$

$M_f = \{B_f[0]\}$ 当且仅当 $B_f[0]$ 是字符串常量表达式。每块取源码行区间 $[\ell_{\text{start}}, \ell_{\text{end}}]$ 并截断到 $L_{\max}$ 字符。**这个式子实际在算什么**：只下探两层——顶层的类与函数、以及类的直接方法子节点。嵌套类、嵌套函数、`if TYPE_CHECKING` 里的定义**不产生自己的块**。

**代码对应。**

| 符号 | 代码 | `file:line` |
|---|---|---|
| $C_f$ | `_chunks_for_file` | `apps/worker/src/dcode_worker/stages/chunk.py:26-41` |
| $B_f$ | `for node in parsed_file.tree.body` | `chunk.py:34` |
| $M_f$ | `_module_doc_chunk` | `chunk.py:44-65` |
| 类块 / 方法块 | `_class_chunk` / `_method_chunks` | `chunk.py:68-81` / `:84-95` |
| 函数块 | `_function_chunk` | `chunk.py:98-115` |
| $[\ell_{\text{start}},\ell_{\text{end}}]$ | `node.lineno` / `_end_line` | `chunk.py:164-171` |
| $L_{\max}$ 截断 | `_cap_content` | `chunk.py:154-161` |
| 保留的元数据 | `file_path · chunk_type · parent_symbol · symbol_name · signature · imports` | `chunk.py:105-115` |

签名重建（`chunk.py:129-147`）用 `ast.unparse`，把跨行 `def` 头、默认值、注解、`*args/**kwargs`、返回类型压成一行完整签名——旧实现取"第一行物理行"会截断（注释 `:132-135`，测试 `test_clone_parse_chunk.py:106`）。

**关键参数。** `max_file_bytes = 1_000_000`（`apps/worker/src/dcode_worker/settings.py:12`）· `max_chunk_chars = 20_000`（`:13`）· 跳过目录 10 个（`stages/parse.py:13-24`）· 截断标记 `"\n... [truncated]"`（`chunk.py:160`）· 排序键 `(file_path, start_line, end_line)`（`chunk.py:22`）。

**复杂度。** 解析 $O(N)$；`_imports_for_node`（`chunk.py:118-126`）对**每个** chunk 做一次 `ast.walk`，真实代价 $O\!\left(\sum_s |T_s|\right) = O(N \cdot d)$，$d$ 为平均嵌套深度。实测 37 文件 / 726 块，瞬时。

**失败模式与兜底。** 文件 >1MB / 非 UTF-8 / 语法错误 → 记 warning 跳过，不失败整轮（`parse.py:43-62`，测试 `test_clone_parse_chunk.py:139`）；单块超 20k → 截断 + 标记（测试 `:153`）。**无兜底的两项**：嵌套函数/嵌套类不产生块（`chunk.py:34-41`），其代码被并入外层块，无法单独检索或引用；`@overload` 产生同名多块（见 §3.2 末）。

### 3.2 符号表与调用边抽取

**直觉。** 给仓库里每个模块/类/函数/方法一个全局唯一的"户口名"（按目录路径拼出来，如 `src.requests.auth.HTTPBasicAuth.__call__`），然后在每个函数体里找所有 `X(...)`，判断被叫的 `X` 是户口簿上的哪一位。判断不出来就**不建边**——宁可漏，不可错。

**数学。** 设内部符号全集 $\Sigma$，别名映射 $A_f$，局部构造类型映射 $\tau$，基类关系 $\beta$。调用解析：

$$
\rho(e)=
\begin{cases}
A_f(e) & e=\mathtt{Name}(n),\ n \in \mathrm{dom}\,A_f \\
m.n & e=\mathtt{Name}(n),\ n \in \mathrm{Local}_f \\
\mathrm{mro}^\star(\kappa, a) & e=\mathtt{self}.a \\
\mathrm{mro}^\star(\tau(v), a) & e=v.a,\ v \in \mathrm{dom}\,\tau \\
p.a & e=v.a \text{ 或 } u.b.a,\ p=\text{解析出的前缀} \\
\bot & \text{否则}
\end{cases}
$$

**所有分支都要求结果 $\in \Sigma$，否则退化为 $\bot$**。其中

$$
\mathrm{mro}^\star(\kappa,a) = \begin{cases}\kappa.a & \kappa.a \in \Sigma\\ \text{BFS}_{\le D}\big(\beta(\kappa)\big)\text{ 的首个命中} & \text{否则}\end{cases}
$$

**这个式子实际在算什么**：六条互斥规则的优先级链，每条都必须落在已知符号集合里才算数。$\mathrm{mro}^\star$ 是 MRO 的**近似而非 MRO**——忽略 C3 线性化，菱形继承中同名方法可能解析到 Python 不会选的那一支。

**代码对应。**

| 符号 | 代码 | `file:line` |
|---|---|---|
| $\Sigma$ | `internal_symbols` | `apps/worker/src/dcode_worker/stages/graph.py:74` |
| 符号构造 | `_symbols_for_file` | `graph.py:142-191` |
| $A_f$ | `_import_aliases_for_file` | `graph.py:448-478` |
| $\mathrm{Local}_f$ | `_module_local_function_names` | `graph.py:481-486` |
| $\tau$ | `_local_variable_types`（**只认 `name = SomeClass()`**，重复赋值丢弃于 `:443-444`） | `graph.py:405-445` |
| $\beta$ | `_bases_by_class`（**先于调用解析计算**，调用顺序 `:81-91`） | `graph.py:349-354` |
| $\mathrm{mro}^\star$ | `_resolve_self_attribute` | `graph.py:363-402` |
| $D = 6$ | `_MAX_BASE_DEPTH` | **`graph.py:360`**，循环 `:389` |
| $\rho$ | `_resolve_call_target` | `graph.py:284-346` |
| 遍历调用点 | `_calls_in_body` | `graph.py:245-281` |

**支持语言：只有 Python。** `parse.py:81` 扫 `*.py`，解析器是 stdlib `ast`（`parse.py:57`）。**代码中未找到任何其他语言的解析路径。**

**四种边**（`packages/shared/src/dcode_shared/schemas.py:57-63`）：

| edge_type | 语义 | 构造 | 实测（`psf/requests`） |
|---|---|---|---|
| `calls` | 函数/方法 → 被调用的内部符号 | `_build_call_edges` `graph.py:772-798` | **303**（当前代码会得 316） |
| `imports` | **模块 → 模块** | `_build_import_edges` `graph.py:748-769`；记录 `:629-640` | 65 |
| `inherits` | 类 → 内部基类 | `_inherits_for_file` `graph.py:493-521` | 33 |
| `references` | 函数体内**作为值使用**（非调用）的内部符号 | `_references_for_file` `graph.py:549-595` | 72 |

**精度取舍三条**：① `calls` 按 `(source, target, line)` 三元组去重（`graph.py:822-831`），因为 `source_line` 要用于 `_source_calls_for_matches` 的行级对齐（`apps/api/src/dcode_api/routes/internal.py:766-789`）；② `references` 只按 `(source, target)` 去重、**丢弃行号**（`graph.py:864-873`）——与 `calls` 不同；③ **不做类型推断**，只认字面量构造（`graph.py:414-419`）。

**复杂度。** $O(N \cdot d)$（每个函数一次 `_local_variable_types` 的 `ast.walk`）；`_resolve_self_attribute` 每次 $O(D \cdot b)$，$D=6$。

**失败模式与兜底。**

| 失败模式 | 兜底 | 证据 |
|---|---|---|
| 环形继承 | `seen` 集合 + 深度上限 6 | `graph.py:387-401`，测试 `test_graph_stage.py:438` |
| 菱形继承同名方法 | **无兜底**，注释自陈是近似 | `graph.py:372-376` |
| 局部变量重新赋值 | **主动丢弃类型，不猜** | `graph.py:439-444`，测试 `:401` |
| 自有 vs 继承同名方法 | 自有优先 | `graph.py:383-385`，测试 `:340` |
| 解析不出目标 | **不建边**；由 API 层 `source_calls` 把未解析表达式**显式暴露**给 LLM | `graph.py:302,343,346`；`internal.py:792-827`；prompt 约束 `apps/agent/src/dcode_agent/llm.py:54-60` |
| **`@overload` 同名符号** | **无兜底**——`_build_symbols`（`graph.py:721-725`）保留**第一条**，而第一条是存根 | 实测 9 个符号 / 20 条记录，见 §4.1 |

### 3.3 Embedding 与向量检索

**直觉。** 为什么代码能变成一串数字？模型读过海量代码，学会了把"意思"压成固定长度的坐标——写 `def parse_url(...)` 和 `def normalize_uri(...)` 即使一个字符都不重合，也会落在坐标空间里相邻的位置。"相似的靠近"就是两个坐标向量夹角很小。检索时把问题也变成坐标，找夹角最小的代码块。

**数学。** 编码器 $E: \text{text} \to \mathbb{R}^d$，$d=768$：

$$
\mathrm{sim}(q,c)=\cos\big(\mathbf{e}_q,\mathbf{e}_c\big)=\frac{\mathbf{e}_q\cdot\mathbf{e}_c}{\|\mathbf{e}_q\|\,\|\mathbf{e}_c\|}
$$

sidecar 编码时已做 L2 归一化，故退化为内积。pgvector 返回**余弦距离** $1-\cos$，代码取 $\mathrm{score}=1-\mathrm{dist}$。

$$
\mathrm{Top}_L^{\text{dense}}(q)=\operatorname*{arg\,min}_{c \in C,\; \mathbf{e}_c \neq \text{NULL}}{}^{(L)}\big(1-\mathrm{sim}(q,c)\big),\qquad L=\max(k,50)
$$

**代码对应。** $E$ 索引侧 `packages/shared/src/dcode_shared/embedding.py:59-77`；$E$ 查询侧 `internal.py:377-384`；L2 归一化 **`apps/embedding/src/dcode_embedding/main.py:72`**；$1-\mathrm{sim}$ **`internal.py:346`**；score `:348`；$\mathrm{Top}_L$ `:351-352`；$L$ `:254`（`_SEARCH_CANDIDATE_LIMIT = 50` at `:51`）；索引类型 **`infra/migrations/versions/001_initial_schema.py:97-100`**；$d$ `001:91` / `db/models.py:128`。

**关键参数。** 模型 `settings.py:45` · $d$ `settings.py:46`（默认 1024，实跑 768）· batch 4 `:48` · 重试 12 `:49` · `max_seq_length` 1024 `dcode_embedding/main.py:45`（Jina 默认 8192 会 OOM，注释 `:41-44`）· **agent 请求的 k = 5** `apps/agent/src/dcode_agent/graph.py:807` · HNSW 的 `m` / `ef_construction` / `ef_search` **未显式设置，用默认值**。

**复杂度。** 索引侧 $O(C/4)$ 次 HTTP 往返（726 → 182 批）；查询侧 1 次编码 + HNSW 近似最近邻 $\approx O(\log C)$。

**失败模式与兜底。** `EMBEDDING_MODEL=stub` → 查询向量 `None` → **dense 完全跳过，退化为纯 sparse**（`internal.py:378-379`、`:343-344`、`:277-283`，测试 `test_internal_routes.py:552`）；sidecar 5xx/连接失败 → 12 次指数退避（`embedding.py:96-122`），4xx **立即抛出不重试**（`:102-108`）；维度不符 → 写库前抛错（`stages/embed.py:150-161`）；**全零向量** → 缓存层当未命中重算（`embed.py:145-146`），且零向量在 pgvector 下距离为 NaN、**排在所有真实值之后，在 top-5 里完全隐形**（migration `003_nonzero_embedding_count.py:17-20`）；HNSW 召回不全 → **无 exact fallback**。

### 3.4 结构信息与语义信息的融合

答案不是"并联"或"串联"，而是：**两处融合，机制不同**。

#### (a) 检索层：sparse ⊕ dense 是并联（加权 RRF）

**直觉。** 两个排序器给出两份榜单，不比较分数（BM25 分和余弦相似度不同量纲），只比较**名次**。名次越靠前贡献越大，且靠前几名之间的差距被压平。

**数学。** 候选集 $D$，稀疏名次 $r_s$、稠密名次 $r_d$（未进榜记 $\infty$，贡献 0），常数 $K=60$、权重 $w_s,w_d$：

$$
\mathrm{RRF}(d)=w_s\cdot\frac{1}{K+r_s(d)}+w_d\cdot\frac{1}{K+r_d(d)}
$$

**这个式子实际在算什么**：把"第几名"换算成 $(0,\frac{1}{K+1}]$ 的贡献值再加权求和；$K$ 越大前几名越平缓。

**代码对应。** $K=60$ `internal.py:52`；$\frac{1}{K+r}$ `_rrf_score` `:542-543`；$r_s$ `:471`；$r_d$ `:472`；$w_s=1.0$ / $w_d=2.0$ `settings.py:54` / `:53`；**整个加法 `internal.py:493-496`**；排序与 tie-break `:508-518`。

$w_d = 2w_s$ 不是拍的：`settings.py:50-52` 记录了理由（等权时 B2 纯稠密的 nDCG 反超 B3 混合），**两种权重各有一个测试钉住**（`test_internal_routes.py:444` 与 `:465`）。

#### (b) 语义证据 ⊕ 结构证据：agent 自行决策 + 事后统一排序

**直觉。** agent 先检索拿到代码块（带源码），可能再调 graph 工具拿到一批位置（**只有 `file:line`，没有源码**）。直接拼给 LLM，带源码的那半必然赢——不是因为更相关，而是因为另一半没东西可读。所以代码做两件事：把 graph 结果**补上源码**，然后让**同一个 cross-encoder** 一视同仁地打分排序。

**数学。** 证据候选 $V=V_{\text{sem}} \cup V_{\text{struct}}$。先水合：

$$
\forall v \in V:\quad \mathrm{content}(v) \leftarrow \begin{cases}\mathrm{content}(v) & \mathrm{content}(v) \neq \varepsilon\\ \mathrm{fetch}(\mathrm{chunk\_id}(v)) & \text{否则}\end{cases}
$$

再统一排序、按预算截断 content（**不截断 ID**）：

$$
V^{\text{ranked}}=\mathrm{sort}_{\downarrow r(q,\cdot)}\big(\{v:\mathrm{content}(v)\neq\varepsilon\}\big)\;\Vert\;\{v:\mathrm{content}(v)=\varepsilon\},\qquad \mathrm{content}(V^{\text{ranked}}_i)\leftarrow\varepsilon\ \ \forall i \ge P
$$

$P=10$。**排序特征里刻意不含 `graph_distance` 与 origin。**

**代码对应。** $V$ `_allowed_evidence` `apps/agent/src/dcode_agent/graph.py:560-685`；水合 `:498-529` → `GET /internal/get_chunks`（`internal.py:121-163`）；批量上限 64 `graph.py:511`；$r$ `:470`；排序 `:474-481`；$P=10$ **`:432`**，应用 `:486-488`；截断而非删除的理由 `:483-485`；**刻意不排序的特征 `:451-454`**；渲染时抹平来源 `:307-325`（注释 `:308-311`）。

"预算 10 对所有 arm 相同"是设计而非巧合：`graph.py:429-431` 写明——B3 最多只有 5 个检索块，所以这个预算**约束的是 B4**，让 graph 证据必须**挤掉**检索证据而不是白送。

**复杂度。** 水合 1 次 HTTP（≤64 id）；rerank $O(|V|)$ 次前向，passage 截到 1000 字符（`graph.py:434,495`）。

**失败模式与兜底。** 水合失败 → 该证据 content 留空、排到未打分尾部（`:519-521`）；reranker 失败 → **退回 observation 顺序**（`:471-472`，测试 `test_graph.py:1274`）；候选 ≤1 → 跳过 rerank（`:467`）；reranker 未配置端点 → **无兜底**，`create_reranker_client` 抛 ValueError 冒泡成 `error`（`reranker.py:124`）。

### 3.5 Rerank

**直觉。** 前面两路是"问题和代码各算一个坐标再比距离"——快，但两者从未见过彼此。cross-encoder 把**问题和代码拼成一段一起读**，所以能判断"这段代码是不是在回答这个具体问题"。代价是每个候选都要跑一次模型。

**与 §3.3 打分的区别：**

| | dense（bi-encoder） | rerank（cross-encoder） |
|---|---|---|
| 输入 | 问题、代码**分别**编码 | 问题+代码**拼在一起**编码 |
| 交互 | 无（只比向量距离） | 全 token 级注意力交互 |
| 可预计算 | 代码向量可离线算好 | **不可**，每对都要现算 |
| 代价 | $O(\log C)$ 近似查找 | $O(n)$ 次模型前向 |
| 用在哪 | 从 726 块选 50 | 从 50 选 16 并重排 |

**数学。** cross-encoder $\phi(q,c)$。取融合后前 $n=16$ 个候选 $P$：

$$
\mathrm{rank}(c)=\big(\phi(q,\pi(c)),\;\mathrm{fused}(c),\;\mathrm{sparse}(c),\;\mathrm{dense}(c),\;\mathrm{path}(c),\;\mathrm{line}(c)\big)\ \text{按字典序降序}
$$

$\pi(c)$ 是截断后的 passage：`symbol_name \n file_path \n content[:256]`。**$P$ 之外的候选不进入最终结果**——重排不是"重新排序全部 50 个"。

**代码对应。** $\phi$ `packages/shared/src/dcode_shared/reranker.py:49-61` → `apps/reranker/src/dcode_reranker/main.py:61-73`；$\pi$ **`internal.py:403-405`**；截断 256 **`internal.py:57`**（注释 `:53-56`：全长 passage 让 10 条 rerank 超 40s，短 passage ~1s）；$n=16$ `settings.py:57`，应用 `internal.py:429`；预排序键 `:421-427`；最终排序键 `:447-456`；`max_length` 512 `dcode_reranker/main.py:42`。

> ⚠️ agent 侧的证据重排（§3.4b）用**另一套常量**：`_RERANK_PASSAGE_CHARS = 1000`（`apps/agent/src/dcode_agent/graph.py:434`）对 `internal.py:57` 的 256，且 agent 侧**不限制候选数**（>1 就全送，`graph.py:467-470`）。同名不同值。

**复杂度。** $O(\min(|C_{\text{fused}}|,16))$ 次 CPU 前向，每次 ≤512 token——**查询路径上最贵的一步**。

**失败模式与兜底。** `RERANKER_MODEL=stub` → `create_reranker_client` 返回 `None` → `_identity_rerank`（`reranker.py:119-120`；`internal.py:416-417`）；5xx/连接失败 → 3 次重试后**降级为 fused 顺序**，只记 warning（`internal.py:433-435`，测试 `test_internal_routes.py:528`）；**`ReadTimeout` 刻意不重试**（`reranker.py:18-22`，白名单 `:81-85`）；identity rerank 的分数依次回落 `fused → dense → sparse`（`internal.py:521-539`）。

### 3.6 ReAct agent 编排

**直觉。** 一个循环：想一步（决定调哪个工具）→ 调 → 看结果 → 再想一步。想不出下一步、或步数用完就停下来写答案。这里的"想"**不是 LLM 在想**——是一张手写规则表在选工具；LLM 只在最后写答案时才出场。

**数学。** 状态 $s=(\mathcal{O},t,\epsilon)$，规划器 $\pi_m(s)\in\mathcal{T}\cup\{\bot\}$：

$$
s_{i+1}=\begin{cases}
\big(\mathcal{O}_i \Vert o(\pi_m(s_i)),\; t_i+1,\; \epsilon_i\big) & \pi_m(s_i)\neq\bot \wedge t_i < T \wedge \epsilon_i=\varnothing\\
\textsf{SYNTHESIZE} & \text{否则}
\end{cases}
$$

$T=14$。**工具失败也让 $t$ 增加**，所以循环长度上界严格是 $T$。

**代码对应。** $T$ **`apps/agent/src/dcode_agent/settings.py:14`**；$\pi_m$ `graph.py:798-812`；mode 表 `apps/agent/src/dcode_agent/state.py:32-44`；转移判定 `graph.py:749-759`；$t$ 递增 `:168`/`:189`；$o(\cdot)$ `:93-172`；图拓扑 `:767-795`。工具签名、终止分支、异常降级见 §2.3–§2.4。

**失败重试**：工具级**无重试**（失败即记 `state.error` 转合成，`graph.py:175-209`）；内部 API HTTP 级**无重试**（`tools/common.py:21-27`）；embedding 12 次；reranker 3 次；LLM **无重试**（失败退模板）；网关→agent **显式不重试**（注释 `deps.py:76-78`：重试会重复已流出的部分答案）。

**复杂度。** 每次查询 $\le 14$ 次工具调用 + 1 次证据 rerank + 1 次 LLM 流式生成。

**失败模式与兜底**（补 §2.4 未覆盖的一条）：规划器完全基于**关键词匹配**——`_needs_multihop` 17 个词（`graph.py:1087-1112`）、`_call_query_direction` 22 个标记（`:1312-1358`）。**不含关键词的架构问题会在第一次检索后直接停止，而外部无法区分"规划器认为没有下一步"和"规划器没看懂"。**

### 3.7 引用验证机制

**直觉。** LLM 写完答案后，把每一处"我引用了某段代码"的标记抠出来，逐个去数据库查它是否真的存在。查不到的**直接从正文里删掉换成占位符**。用户看到的每一条引用都是查证过的。

**验证什么**——三类 token，两套协议：

| 协议 | 触发条件 | 认作引用的 token | 位置 |
|---|---|---|---|
| **catalog**（LLM 路径） | `evidence_catalog` 非 `None` | `[C1]` 这类服务端 ID + 显式 `path.py:42` | `apps/agent/src/dcode_agent/groundedness.py:140-218` |
| **legacy**（模板 / 历史产物） | `evidence_catalog is None` | 反引号点分名 + `path.py:42` | `groundedness.py:117-137` |

关键设计：catalog 模式下**普通反引号内联代码不算引用**（`groundedness.py:150-151`）——`self.client.retrieve` 是代码格式化，不是证据主张。系统 prompt 要求 ID 放在反引号之外（`apps/agent/src/dcode_agent/llm.py:48-49`）。

**怎么判定通过。**

| 形态 | 判定 | 位置 |
|---|---|---|
| `file.py:42` | 存在 chunk 满足 `file_path = ? AND start_line ≤ 42 ≤ end_line`，按 `(start_line DESC, end_line ASC, id)` 取**最窄包含块** | `groundedness.py:275-301` |
| 点分符号 | SQL 缩小到超集（`candidate_filter`），Python 决定（精确优先，否则 `.suffix` 匹配） | `groundedness.py:304-340` → `packages/shared/src/dcode_shared/symbols.py:38-53` / `:56-64` |
| `[C#]` | 查 catalog → 服务端 token → 按上两条之一验证 | `groundedness.py:228-247` |
| `[C#]` 不在 catalog | **直接判失败** | `groundedness.py:184-194`，测试 `test_groundedness.py:277` |

`symbols.py:56-64` 的 `autoescape=True` 值得单说：Python 标识符里 `_` 极常见，而 `_` 在 SQL `LIKE` 里是单字符通配符。不转义则 `api._get` 会匹配 `api.aget`、`api.bget`——**守卫里的静默假阳性**。

**失败时前端收到什么。** 未验证引用从正文抹掉换占位符（`groundedness.py:347-348`、`:407-426`）；只有已验证引用进 `state.citations`（`graph.py:727-738`）——**未验证引用不产生 `citation` 事件**；分数低于阈值追加脚注，且**区分"引用全失败"与"什么都没引用"**（`:381-397`）；`final_answer.groundedness` 携带分数 → Trace 药丸（`Trace.tsx:75-82`）。

**复杂度。** 每条引用 1 次 SQL。file:line 走 `ix_chunks_repo_file`；符号用 `LIKE '%.name'`——**`endswith` 无法走索引，是一次顺序扫描**。727 行可忽略，大仓库会是热点。

**失败模式与兜底。** `db is None` 或 `repo_id` 非 UUID → 全部标未验证（`:125-127`、`:174-177`、`:250-254`）；抹除时误伤更长路径 → 边界守卫正则含 `/` 和 `-`（`:441-449`，测试 `:427`）；`[C1][C2]` 相邻 → 替换前先插空格，否则 Markdown 会合成一个畸形 code span（`:429-438`，测试 `:338`）；**DB 查询本身失败 → 无兜底**，冒泡成 `error` 事件，用户拿不到答案。

### 3.8 Groundedness 打分

**直觉。** 分数就是**抹除之前**查得到的引用比例——所以一个被大量涂抹的答案仍然是低分，涂抹不能洗白。

**数学。** 草稿 $a$，抽取的引用序列 $R(a)=(r_1,\dots,r_n)$，索引验证谓词 $v$：

$$
g(a)=\begin{cases}\dfrac{1}{n}\displaystyle\sum_{i=1}^{n} v(r_i), & n > 0\\[2ex] 0, & n=0 \quad \text{(约定，非推导)}\end{cases}
$$

**这个式子实际在算什么**：已验证引用占全部引用的比例。$n=0$ 取 0 是**刻意选择的约定**——取 1 会让"什么都不引用"拿满分（完整推理在 `groundedness.py:257-272`，含"为什么也不选从分母剔除"）。

**代码对应。** $R(a)$ catalog 模式 `:152-165`、legacy 模式 `:78-91`；$v$ file:line `:275-301`、符号 `:304-340`；$g(a)$ **`:217-218`**（catalog）/ **`:135-136`**（legacy）；$n=0$ 约定 **`:272`**；涂抹 `:407-426`；分数取**涂抹前** `:403`；阈值 $\tau=0.95$ `packages/shared/src/dcode_shared/settings.py:42`，比较 `:381`。

**打分不用 prompt**——它是纯 SQL 验证，没有 LLM 参与。有 prompt 的是**约束模型怎么写引用**：`apps/agent/src/dcode_agent/llm.py:43-53` 五条强制规则（其中 `:44-45` 告诉模型不在目录里的 ID 会被剥离并拉低分数），`:54-60` 另有三条调用图诚实性规则。

**如何影响输出。**

| 分数 | 行为 | 位置 |
|---|---|---|
| 任意 | 未验证引用**一律**抹除 | `:376-380` |
| $<0.95$ 且有引用 | 追加"引用可信度 X 低于 0.95，已移除 N 个" | `:390-396`、`:481-501` |
| $<0.95$ 且**无**引用 | 追加**另一条**脚注 | `:388-389`、`:463-478` |
| $\ge 0.95$ | 不加脚注，抹除照常 | 测试 `test_groundedness.py:491` |

两条脚注分开的理由在 `:382-386`：无引用答案得 0.0，若显示"已移除 0 个引用"，逐字为真而整体误导。

**一处内部不一致**：空引用时 legacy 路径是 `... if checks else **1.0**`（`:136`），catalog 路径是**无保护的**除法（`:218`）。两条都靠上游早返回 `_uncited_result()`（`:119`、`:167`）保证 `checks` 非空，当前不可达；但**若有人改动早返回，一条会静默返回 1.0，另一条会 ZeroDivisionError**。

**复杂度。** $O(|R(a)|)$ 次 SQL；抹除是 $O(|R(a)|\cdot|a|)$ 的正则替换。

### 3.9 评测指标

#### (a) baseline 阶梯：每级实际跑什么

| arm | 类 | 检索 | 答案 | mode | 入 H1 决策 | 证据 |
|---|---|---|---|---|---|---|
| **B0** | `GithubSearchBaseline` | 外部 GitHub code search | 模板 | — | **否** | `baselines/__init__.py:41` |
| **B1** | `BM25Baseline` | `mode=sparse` | **模板**，groundedness **硬编码 1.0** | — | **否** | `baselines/bm25.py:14,18` → `common.py:37` |
| **B2** | `VanillaRAGBaseline` | agent 内 `mode=dense` | **共享 agent 合成 + 守卫** | `dense_only` | 是 | `state.py:43`；`common.py:89-98` |
| **B3** | `HybridRAGBaseline` | `mode=hybrid` | 同上，**无工具扩展** | `hybrid_only` | 是 | `state.py:40`；`common.py:101-104` |
| **B3.5** | `HybridAgentNoGraphBaseline` | hybrid | 同上，**有 read_file/get_file_outline，无 graph 工具** | `agent_no_graph` | **否（诊断）** | `state.py:38`；`common.py:107-116` |
| **B4** | `FullSystemBaseline` | hybrid | 同上，**全部工具** | `full` | 是 | `state.py:34`；`common.py:119-122` |

判定：`_h1_report`（`run.py:544-602`），阈值 `0.05`（`:545`），比较层 `("L2","L3")`（`:546`），合取（`:560`）。B3.5 只进 `diagnostics`（`:599-601`、`:605-643`）。

#### (b) 计分协议 `uniform_final_verified_evidence_v2` 的确切定义

**v2 的全部内容就是取消不对称。** `run.py:83` `scores_final_evidence = baseline_id in AGENT_BASELINES`，而 `AGENT_BASELINES = frozenset({"B2","B3","B3.5","B4"})`（`baselines/__init__.py:31`）。**B3 现在也按 final verified evidence 打分**，不是 top-5。

| arm | 被打分集合 | 字段 | 上限 | 实测大小（repeat-1，min/中位/max） |
|---|---|---|---|---|
| **B0** | 检索到的 file 列表 | `retrieved_files[:k]` 去重（`run.py:100`） | 5 | — |
| **B1** | 检索 top-k chunk | `retrieved_chunk_ids[:k]`（`:78`） | 5 | 5 / 5 / 5 |
| **B2** | 答案中已验证的引用证据 | `final_evidence_chunk_ids[:k]`（`:79`） | 5 | 1 / 4 / 5 |
| **B3** | 同上 | 同上 | 5 | **2 / 3 / 5** |
| **B3.5** | 同上 | 同上 | 5 | 1 / 3 / 5 |
| **B4** | 同上 | 同上 | 5 | **2 / 4 / 5** |

`final_evidence_chunk_ids` 由 `_verified_evidence_chunk_ids`（`run.py:478-488`）构造：遍历 `answer.evidence`，**跳过 `verified=False` 和 `chunk_id is None`**，按答案中出现顺序去重。

**v1 vs v2 的实际差别**（我用已提交的 `candidate_*` 与 `final_evidence_*` 两套指标算的）：

| | L2 · B4−B2 | **L2 · B4−B3** | L3 · B4−B2 | L3 · B4−B3 | 判定 |
|---|---|---|---|---|---|
| **v1**（B4 用 final，B2/B3 用 top-k） | +0.2115 | **+0.0822** | +0.2730 | +0.1473 | 四项全过 → **`supported`** |
| **v2**（官方，全部用 final） | +0.1363 | **+0.0439** | +0.2474 | +0.1693 | L2 差 0.0061 → **`unsupported`** |

**在这份记录数据上，是预注册的 v2 协议让结论从 supported 变成 unsupported。** 规则对各 arm 的影响（`final_evidence` 减 `candidate`）：B2 +0.075/+0.026、B3 +0.038/**−0.022**、B3.5 +0.060/+0.125、**B4 +0.082/+0.147**——**B4 获益最多**。

但规则有一处真实代价：`run.py:79` 的 `[:k]` 截断。repeat-1 的 B4 有 2 道题命中，**其中 q-009 被丢掉的第 6 条正是 gold**（详见 §3.9d）。

#### (c) taxonomy 与题集来源

`taxonomy` 是 JSONL 里的**人工标注字段**（`questions/models.py:21`，取值域 `:7`），**代码中没有任何判定器**；唯一的自动检查是计数（`test_questions_dataset.py:43-50`）。分层定义只在 `questions/README.md:74-78`。

`graph_reverse` 的 17 题**没有生成脚本**——全仓 grep 只命中读取方与文档。构造过程只在 commit `ae47419` 的 message 里："reverse-constructed from the indexed call relationships and source of the current corpus"。**走了哪些 `edge_type`：代码中未找到。** 唯一可执行的相关代码是**校验**：`questions/resolve.py:52-71` 解析锚点，`:83-112` 命中唯一性（**0 命中 raise `:99-103`，多命中 raise `:109-112`**）。

#### (d) 三个指标：定义、相关性口径、实现偏离

**relevance 是二值的**——三个函数都只做 `cid in gt` 的成员判断（`metrics/retrieval.py:18`、`:25`、`:35`），`gt` 是 `set[str]`。

**Recall@k**

$$\mathrm{Recall@}k=\frac{\big|\{r \in R_{1..k}\}\cap G\big|}{|G|}$$

*手算例（真实数据，q-009 / B4 / repeat-1）：*
```
G = {8622e80a, 7a1cd3f6, faa4005b}                        |G| = 3
R = [8622e80a, 74800451, 6b96fa89, b51020d0, 7a1cd3f6]    （已被 [:5] 截断）
     ↑命中1                                    ↑命中5      命中 = 2
Recall@5 = 2 / 3 = 0.666667      ← 与记录值逐位一致
```
实现 `retrieval.py:11-19`。**偏离 1**：`if not gt: return 1.0`（`:16-17`），空 gt 返回 1.0；本数据集 33 题全有 gt，从不触发。**偏离 2**：同样是空 gt，`ndcg_at_k` 返回 **0.0**（`:38`）——同一模块两种真空约定。与标准定义**一致**。

**MRR**

$$\mathrm{RR}=\begin{cases}\dfrac{1}{\min\{i : R_i \in G\}} & \exists i,\ R_i \in G\\[1ex] 0 & \text{否则}\end{cases}\qquad \mathrm{MRR}=\frac{1}{|Q|}\sum_{q}\mathrm{RR}(q)$$

*手算例：* 同上，第 1 位即命中 → $\mathrm{RR}=1/1=1.000000$（与记录值一致）。换一个：`R=[X,A,Y,B,Z]`、$G=\{A,B\}$ → 首个命中在第 2 位 → $\mathrm{RR}=0.5$。**注意 B 在第 4 位对 RR 毫无贡献**——这是定义特性不是 bug。

实现 `retrieval.py:22-27`。**偏离 1（命名）**：函数叫 `mrr` 但算的是单题 RR，求平均在 `run.py:438`。**偏离 2（签名缺 k）**：`mrr(retrieved, gt)` **没有 k 参数**，`:24` 遍历整个列表。当前无害——调用点传的都已截断（`run.py:139`/`:147`/`:151`，截断在 `:78`/`:84-88`/`:100`）；**但未来调用方传未截断列表会静默得到 MRR@∞**。

**nDCG@k**

$$\mathrm{DCG@}k=\sum_{i=1}^{k}\frac{rel_i}{\log_2(i+1)}\qquad \mathrm{IDCG@}k=\sum_{i=1}^{\min(|G|,k)}\frac{1}{\log_2(i+1)}\qquad \mathrm{nDCG@}k=\frac{\mathrm{DCG@}k}{\mathrm{IDCG@}k}$$

**IDCG 约定**：理想排序把 $\min(|G|,k)$ 条相关项放最前——标准的"IDCG@k 截断于 k"。

*手算例（同 q-009，白板可推）：*
```
G = 3 条，命中位置 {1, 5}，k = 5

DCG  = 1/log₂(1+1) + 1/log₂(5+1)
     = 1/log₂2     + 1/log₂6
     = 1/1         + 1/2.5849625
     = 1 + 0.3868528 = 1.3868528

IDCG = 1/log₂2 + 1/log₂3 + 1/log₂4          （min(3,5)=3 条理想排在位 1,2,3）
     = 1 + 0.6309298 + 0.5 = 2.1309298

nDCG@5 = 1.3868528 / 2.1309298 = 0.650821   ← 与记录值逐位一致
```
实现 `retrieval.py:30-38`。DCG 用 `1.0/math.log2(i+2)`、`i` 从 0 起（`:33-34`）→ 位置 $p=i+1$、分母 $\log_2(p+1)$，**与标准一致**。增益是二值（`:35`），即 $\sum rel_i/\log_2(i+1)$ 形式而非 $\sum(2^{rel_i}-1)/\log_2(i+1)$——**二值相关下两者等价，无偏离**。IDCG 用 `min(len(gt), k)`（`:37`），**标准约定**。**偏离**：`ideal_dcg == 0` 时返回 0.0（`:38`），与 `recall_at_k` 的 1.0 不一致。重复项会重复计分，但上游已去重（`run.py:481-488`、`:463-475`），当前不触发。

#### (e) composite 与判定

$$\mathrm{Composite}(\text{arm},\ \ell)=\tfrac13\Big(\overline{\mathrm{Recall@}k}+\overline{\mathrm{RR}}+\overline{\mathrm{nDCG@}k}\Big)$$

$$\textsf{H1 supported}\iff \bigwedge_{\ell\in\{L2,L3\}}\Big[\big(C_{B4}^{\ell}-C_{B2}^{\ell}\ge 0.05\big)\wedge\big(C_{B4}^{\ell}-C_{B3}^{\ell}\ge 0.05\big)\Big]$$

`run.py:437-439`（各项均值）、`:666`（三项）、`:669-670`（composite）、`:559-560`/`:588`（判定）。三次重复时先按题平均再聚合（`_mean_across_repeats` `:320-395`），并单独记录每次重复的独立判定（`:283-298`）。

**复杂度。** 三个指标都是 $O(k)$；整轮 $5 \times 3 \times 33 = 495$ 次 agent 调用。

**本节小结**：这一层解决的是"每一个显示给用户或写进报告的数字，都能沿着一条 `file:line` 链回到它被计算出来的那一行"。

---

## 4. 可引用数字台账

**来源等级**：**A** = 已提交产物字段可直接核对（给出 json 路径 + key）· **B** = 已提交源码常量或配置（`file:line`）· **C** = scratchpad 重算（脚本 `call_ratio.py`，输入语料 commit `414f0513…`；或 `wc -l` / `pytest --collect-only` / `npm test` 实跑）· **D** = 依赖运行中的 Postgres 或本机 `.env`，仓库里核对不到。

> **最后一列是硬要求。** 找不出这么一句话就能安全说出口的数字，一律进 §4.9 不可引用清单。

### 4.1 语料与索引规模

| 数值 | 含义 | 证据位置 | 等级 | **必须同时说的那句话** |
|---|---|---|---|---|
| **726** | chunk 总数 | `provenance.json` → `corpus.chunks`；离线重算同值 | **A**(C) | 「拆成 method 489 / function 146 / class 72 / module_doc 19，按 Python AST 边界切」 |
| **473** | edges 总行数 | `provenance.json` → `corpus.edges` | **A** | 「**四种边之和，调用边只有 303**」 |
| **303** | `calls` 边 | `SELECT edge_type, count(*)` | **D**(C) | 「**这是库里的值；当前代码重索引会得 316，多 4.3%，需要重索引才生效**」 |
| **72 / 65 / 33** | `references`/`imports`/`inherits` | 同上 | **D**(C 一致) | 「这三种边用当前代码重算逐项相同，只有 `calls` 变了——差异被定位在调用解析这一个函数上」 |
| **724** | symbol 总数 | DB；离线重算 744 → 去重 724 | **C+D** | 「744 条原始记录去重得 724，**丢掉的 20 条全是 `@overload` 存根**」 |
| **2615** | 解析器访问到的 `ast.Call` 点 | `call_ratio.py`（复刻 `stages/graph.py:265-281`） | **C** | 「分母是 worker 真正遍历到的调用点，不含模块级语句和嵌套类的方法」 |
| **316 / 12.1%** | 当前代码解析成功数 / 解析率 | 同上 | **C** | 「**12% 是"无类型推断的纯静态 AST 分析"的合理量级，不是 bug**——1076 个未解析是 `obj.X()` 型，需要类型推断」 |
| **1076/897/226/92/5/3** | 未解析的六类分布 | 同上 | **C** | 「最大一类是接收者类型未知，这是明确声明放弃的能力（`stages/graph.py:414-419`）」 |
| **37** | 参与索引的 `.py` 文件数 | 同上 | **C** | 「0 个因超 1MB / 解码 / 语法错误被跳过——本语料没有触发跳过路径」 |
| **62** | 33 题去重后的 gold chunk 数 | 由 `repeat-1/B4/per_question.jsonl` 的 `gt_chunk_ids` 聚合 | **A** | 「62/62 都在索引里、都有非零向量、都不在 test 路径——**recall 的数学天花板确实是 1.0**」 |
| **9 / 20** | 重复 qualified_name 数 / 被丢弃记录数 | 重算 + DB 验证 | **C+D** | 「全部是 `@overload` 存根，**保留的是第一个存根而不是真实现**，影响 2.8% 的 chunk」 |
| **2 / 44 / 453** | gold chunk 行数 min/均值/max | DB | **D** | 「8 条 ≤5 行（7 个异常类 + 1 个函数），453 行的是 `Response` 类——两端都对检索不利」 |
| `414f0513…` | 语料 commit | `provenance.json` → `corpus.commit_sha` | **A** | 「库里有 5 行 psf/requests、两个不同 commit；只有这个 commit 那批是 473 边」 |

### 4.2 检索与模型参数

| 数值 | 含义 | 证据位置 | 等级 | **必须同时说的那句话** |
|---|---|---|---|---|
| **768** | embedding 维度 | `provenance.json` → `corpus.embedding_dimensions` | **A** | 「**代码和 compose 默认都是 1024**；维度在 alembic 执行那一刻烧进列定义，改维度必须重建库」 |
| **1024** | 代码默认维度 | `settings.py:46`；`docker-compose.yml:60` | **B** | 「实际跑的是 768，不一致是本机 `.env` 覆盖的结果」 |
| **60** | RRF 常数 K | `internal.py:52` | **B** | 「融合只比名次不比分数——BM25 分和余弦相似度不同量纲，加不到一起」 |
| **2.0 / 1.0** | dense/sparse 权重 | `settings.py:53-54`；加法 `internal.py:493-496` | **B** | 「等权时 B2 纯稠密的 nDCG 会反超 B3 混合，**两种权重各有一个测试钉住**」 |
| **50** | 单路候选池 | `internal.py:51`，应用 `:254` | **B** | 「两路各取 50 再融合，最终只返回 5」 |
| **16** | reranker 候选上限 | `settings.py:57`，应用 `internal.py:429` | **B** | 「**16 名之外的候选直接出局，rerank 不是重排全部 50 个**」 |
| **256** | rerank passage 截断（API 侧） | `internal.py:57` | **B** | 「agent 侧同名常量是 1000（`graph.py:434`），两处不同」 |
| **5** | agent 请求的 k | `graph.py:807` | **B** | — |
| **1.2 / 0.75** | BM25 `k1`/`b` | `bm25.py:16-17`；`run_config.json` → `sparse_retrieval` | **A+B** | 「**BM25 是应用层纯 Python，不走 `chunks.tsv` 和 GIN——那两个建了但没人写**」 |
| **8** | BM25 语料 LRU 容量 | `retrieval/bm25.py:16` | **B** | 「每个 `(repo_id, index_revision)` 首查要把整个仓库拉进进程建索引——**明确的规模上限**」 |
| **20s / 3** | reranker 超时/重试 | `reranker.py:23-24`；`settings.py:58` | **B** | 「`ReadTimeout` 刻意不重试——重试慢的 CPU 推理只会让单线程模型服务更慢」 |
| **12** | embedding 重试 | `settings.py:49` | **B** | 「4xx 立即抛出不重试，只重试 5xx 和连接错误」 |
| **1024** | embedding `max_seq_length` | `dcode_embedding/main.py:45` | **B** | 「Jina v2 默认 8192，那个开销会 OOM 掉 sidecar（注释 `:41-44` 记录了这次事故）」 |
| 三个模型名 | 真实模型 | `provenance.json` → `models` | **A** | 「**judge 仍是 `stub`**，所以答案质量没有测量，只有检索和引用被测了」 |

### 4.3 Agent 编排参数

| 数值 | 含义 | 证据位置 | 等级 | **必须同时说的那句话** |
|---|---|---|---|---|
| **14** | 工具步数上限 | `apps/agent/src/dcode_agent/settings.py:14` | **B** | 「**从 8 提上来的**——B4 的扩展把 8 跑满了，走到上限是截断假象而不是策略」 |
| **11** | 工具总数 | `tools/__init__.py:25-37` | **B** | 「其中 6 个是 `GRAPH_TOOLS`，而**这 6 个里有 4 个在记录的三次重复里从未产出过任何被引用的证据**」 |
| **10** | 证据上下文预算 | `graph.py:432` | **B** | 「对所有 arm 相同——约束的是 B4：graph 证据必须挤掉检索证据才能进上下文，不是白送」 |
| **1200** | 单条证据字符上限 | `graph.py:292` | **B** | — |
| **64** | 证据水合批量上限 | `graph.py:511`；服务端 `internal.py:124` | **B** | — |
| **6** | 基类 BFS 深度上限 | `stages/graph.py:360` | **B** | 「是 MRO 的近似不是 MRO，忽略 C3 线性化，菱形继承可能选错分支」 |
| **0.95** | groundedness 阈值 | `provenance.json` → `groundedness_guardrail`；`settings.py:42` | **A+B** | 「**低于它只是加一条脚注；未验证引用无论分数多少都会被从正文抹除**」 |
| **6 / 2000 / 4000** | history 轮/总字符/单轮字符 | `api/settings.py:15-17` | **B** | 「在网关截断一次，让规划器、转发 body、缓存键看到同一份」 |
| **700 / 0.1** | 合成 max_tokens/temperature | `agent/settings.py:24-25` | **B** | 「**temperature 不是 0，所以合成是随机的——这正是需要跑三次重复的原因**」 |
| **24h/1h/7d/永久** | 四种缓存 TTL | `settings.py:35/34/36`；`cache.py:14` | **B** | 「工具缓存 24h 意味着换了 agent 代码必须先 `FLUSHALL`，否则会拿到旧代码的结果」 |

### 4.4 评测协议与题集

| 数值 | 含义 | 证据位置 | 等级 | **必须同时说的那句话** |
|---|---|---|---|---|
| **33 = 5/16/12** | 题数与分层 | `provenance.json` → `execution.question_counts`；`test_questions_dataset.py:50` | **A+B** | 「**taxonomy 是人工标注的字段，代码里没有任何判定器**」 |
| **16 / 17** | manual/graph_reverse | `questions.jsonl` 的 `source`；`test_questions_dataset.py:34` | **A+B** | 「**graph_reverse 没有生成脚本，构造过程只存在于 commit `ae47419` 的 message 里**」 |
| `db813124…` | 题集 sha256 | `provenance.json` → `question_set.sha256`；`shasum` 复验一致 | **A** | 「跑之前冻结，`ae47419` 的 message 里也写了同一个值」 |
| **2.12/1.38 vs 4.29/2.94** | manual vs graph_reverse 平均 gold/跨文件数 | scratchpad 现算 | **C** | 「**graph_reverse 的 gold 集合大一倍且全是 L2/L3——taxonomy 和 source 在这份数据里分不开**」 |
| **0.05** | H1 阈值 | `run.py:545`；`h1_report.json` → `threshold` | **A+B** | 「**是合取**：两层 × 两个对手，四个比较全过才算 supported」 |
| **3** | 重复次数 | `run_config.json` → `repeats` | **A** | 「检索是确定的，随机的是合成——所以重复测的是合成方差」 |
| **5** | 检索截断 k | `run_config.json` → `k` | **A** | 「有 9 道题的 gold 数是 5，等于说要全对必须 top-5 一个不错」 |
| `…_v2` | 计分协议名 | `run.py:39`；`run_config.json` → `scoring_protocol` | **A+B** | 「**v2 的全部内容就是让 B2/B3/B3.5/B4 用同一条规则**——按答案里已验证的引用打分，不是按 top-5」 |
| **6 个** | `GRAPH_TOOLS` 大小 | `graph_tools.py:58-67` | **B** | 「一个定义两个消费者共用（B3.5 禁用清单 + 评测 origin 计数），此前两边不一致过」 |

### 4.5 评测结果

| 数值 | 含义 | 证据位置 | 等级 | **必须同时说的那句话** |
|---|---|---|---|---|
| **`unsupported`** | H1 判定 | `h1_report.json` → `decision` | **A** | 「**四个比较过了三个**，B4 vs B3 在 L2 差 0.0061」 |
| **+0.1363 / +0.0439** | L2 的 B4−B2 / B4−B3 | `h1_report.json` → `comparisons.L2.*` | **A** | 「0.0439 低于 0.05；它在三次重复间的极差是 0.083，**比 0.05 的门槛本身还宽**」 |
| **+0.2474 / +0.1693** | L3 的 B4−B2 / B4−B3 | → `comparisons.L3.*` | **A** | 「L3 是稳的：三次重复**单独都过**（+0.132 / +0.175 / +0.201）」 |
| **0.0061** | L2 距门槛差额 | 由 `threshold` 与 `margin_vs_B3` 相减 | **A** | 「对应的重复间标准差是 0.034，**差额只有噪声的 1/5.6**，再调系统也归因不到调优上」 |
| **0.034** | 重复间标准差 | `provenance.json` → `limitations[1]`；复算 `pstdev = 0.034088` | **A**(C 标口径) | 「**这是总体标准差口径；样本标准差（n−1）是 0.042**」 |
| **+0.0376/+0.0057/+0.0884** | 三次重复各自 L2 B4−B3 | → `per_repeat[i].comparisons.L2.margin_vs_B3` | **A** | 「极差 0.083 比门槛还宽——**单次运行分不出真实效应和模型这次碰巧怎么措辞**」 |
| **+0.0218 / +0.0226** | L2/L3 调用图孤立贡献 | → `diagnostics.per_taxonomy.*.graph_margin_B4_vs_B3.5` | **A** | 「**这是诊断项，明确排除在决策之外**；同层的 agent-loop 项在 L3 是 +0.147，是它的六倍多」 |
| **+0.1466** | L3 的 agent 循环贡献 | → `agent_loop_margin_B3.5_vs_B3` | **A** | 「**B4 的优势主要来自多步取证，不是调用图**——只有 B3.5 这个消融能把两者分开」 |
| **1.000** | 五个 arm 的 groundedness | `suite_summary.json` → `{arm}.groundedness` | **A** | 「**B1 的 1.0 是 `baselines/common.py:37` 的字面量，B2–B4 的是实测**；且只有配上 `answers_without_citations = 0` 才有意义」 |
| **0** | `answers_without_citations` | `suite_summary.json` | **A** | 「必须和 groundedness 并排说——没引用和引用全错都得 0.0，只有这个计数能分开」 |
| **4/3** | 去掉 groundedness 项的放大倍数 | `run.py:648-665`；`0.0329284984228323 × 4/3 = 0.0439046645637764` 精确验证 | **A+B** | 「**等价于把门槛从 0.050 降到 0.0375，这是一次被诚实标注的降标准**；四项口径同样是 unsupported」 |
| **`unsupported`（四项）** | 旧口径判定 | → `comparisons.*.four_term.supported` | **A** | 「两种口径都不通过，所以那次改动没有改变这次的结论」 |
| **12/12/12 与 14/12/16** | 旧 origin 集合下 B3.5/B4 的 graph gt 命中 | `repeat-{1,2,3}/{arm}/per_question.jsonl` → `new_gt_hits_from_structural_evidence` | **A** | 「**这是被废弃的旧集合的值**——它给没有调用图的 B3.5 打 12 分，所以它测的不是调用图」 |
| **0/0/0 与 4/3/5** | 新 origin 集合下同一量 | `graph_tools.py:29-31`(B)；按 `run.py:491-513` 重算逐位一致(C) | **B+C** | 「**这是重算值，不是任何已提交字段**；已提交的 `per_question.jsonl` 里只有旧集合的数」 |
| **440/248/152/111/36** | B4 三次合计的被引用证据来源计数 | 由 `repeat-*/B4/per_question.jsonl` 的 `final_evidence[].origins` 聚合 | **A** | 「**`get_call_neighbors`、`find_definition`、`get_dependencies`、`get_dependents` 四个 GRAPH_TOOLS 一次都没出现**」 |
| **9/16 vs 10/17** | 引用了 graph 来源证据的题目比例 | 同上 | **A** | 「两者几乎相同——**graph_reverse 题目并没有更多地触发调用图**」 |
| **+0.0283 vs +0.0183** | manual(L2+L3) vs graph_reverse 的 B4−B3.5 | 按 `source` 切分重算 | **C** | 「调用图在 graph_reverse 题上贡献**更小**——但这只说明偏置没在指标上兑现，**不等于没有偏置**」 |
| **9/33** | repeat-1 里 B4 的 recall 天花板 <1.0 的题数 | 计算 `min(|final_evidence|,5) < |gt|` | **C** | 「**这些题不是没检索到，是答案引用的条数不够**——v2 口径下 recall 被引用密度封顶」 |
| **q-009: 6→5，丢的第 6 条是 gold** | `[:k]` 截断的真实代价 | `repeat-1/B4/per_question.jsonl` 的 `q-009` 行 | **A** | 「B4 找到了全部三条正确证据、都验证通过、都写进了答案，**指标只承认前五条**，recall 从 1.0 变 0.667」 |
| **0.667/1.000/0.6508** | q-009 的三个指标 | 同上；手算逐位复现 | **A+C** | 「三个指标我都在这道题上手算复现过记录值，公式实现无偏离」 |
| **0** | 观测到的 api/agent 错误数 | `provenance.json` → `execution.api_agent_errors_observed` | **A** | 「这是"观测到"不是 harness 写的字段——文件顶部第 2 行专门声明了这一点」 |
| **B1 三次完全相同** | 检索确定性 sanity check | `repeat-*/B1/metrics.json` 三份逐位相同 | **A+C** | 「这证明重复间方差来自合成而非检索——**B2 的 recall 也三次相同，只有 mrr/ndcg 变，说明变的是引用顺序不是引用集合**」 |

### 4.6 工程规模与质量

| 数值 | 含义 | 证据 | 等级 | **必须同时说的那句话** |
|---|---|---|---|---|
| **291** | pytest 用例数 | `pytest --collect-only` 实跑 | **C** | 「未跑执行，只做了收集——我没有声称它们全绿」 |
| **73 / 16** | vitest 用例/文件数，全绿 | `npm test -- --run` 实跑 1.14s | **C** | 「**CLAUDE.md 写的 71 已过时**」 |
| **10952 / 7678** | Python 源码/测试行数 | `wc -l` | **C** | 「排除了 `node_modules` 下 16 个共 1743 行的 `.py`，不排除会虚增到 12695」 |
| **4746 / 1445** | 前端源码/测试行数 | `wc -l` | **C** | 「测试行数接近源码的三分之一，多数钉的是诚实性契约不是渲染」 |
| **7** | uv workspace 成员数 | `pyproject.toml:8-16` | **B** | 「四个应用包之间零 Python import，只通过 HTTP/AMQP/SQL/Redis 通信」 |
| **6 + 2** | compose 常驻服务 + profile sidecar | `docker-compose.yml:132-133`、`:153-154` | **B** | 「**`make up` 不会启动 embedding/reranker**，必须先跑两个 host 脚本」 |
| **4 + 1** | 运行时表 + 溯源表 | `db/models.py`；migration `002_index_runs.py` | **B** | 「**`index_runs` 建了 append-only 触发器，但代码里没人写它**——`db/models.py:7-11` 自己记着」 |

### 4.7 B0（外部 GitHub 检索）

| 数值 | 含义 | 证据 | 等级 | **必须同时说的那句话** |
|---|---|---|---|---|
| **0.3081/0.2955/0.2841** | B0 的 file 级 recall/mrr/nDCG | `results/eval-b0-2026-07-31/metrics.json` → `file_*` | **A** | 「**是 file 级；而记录的 H1 那次运行里没有任何 arm 有 file 级指标（那个 commit 晚了 21 分钟），所以这三个数在仓库里没有可比对象**」 |
| **0.6364 / 12** | B0 的 groundedness / 无引用答案数 | 同上 | **A** | 「**12/33 的答案根本没有引用**，所以这个 0.636 不能和其他 arm 的 1.000 并排看」 |
| **33** | B0 题数 | 同上 → `questions` | **A** | 「同一份冻结题集，但 B0 查的是**实时外部索引，产物不可复现**」 |

### 4.8 两处主动质疑

**(a) 473 条边对 `psf/requests` 是否偏低？**

先纠正问题本身：**473 不是调用图**。库里是 `calls 303 / references 72 / imports 65 / inherits 33`。

用 worker 自己的函数在 `414f051` 上离线重跑，funnel 是：

```
py 文件                                    : 37   （0 个被跳过）
1. 解析器访问到的 ast.Call 点              : 2615
2. 解析成内部符号的                        :  316   ← 12.1%
3. _unique_calls (src,tgt,line) 去重后     :  316
4. 符号 join / 自环 / 重复丢弃后           :  316   （三项各丢 0）
```

未解析的 2299 个分布：`obj.X()` 接收者类型未知 **1076** · 裸 `Name()`（builtin/标准库/三方）**897** · `a.b.X()` 前缀只支持一层 **226** · 接收者是表达式 **92** · `self.X()` 类与基类都找不到 **5** · callee 非 Name/Attribute **3**。

**判断：303 对"纯 Python 静态 AST、无类型推断、无 import 解析器"是合理量级，不是 bug。** `requests` 重度面向对象，1076 个 `obj.X()` 大多是 `self.<attr>.method()`、`response.raw.read()` 这类——解决它们需要类型推断，而这是明确声明放弃的能力（`stages/graph.py:418-419`）。

**顺带一个未预期的发现**：其他三种边**完全一致**（`inherits 33` / `references 72` / `imports 65`，chunks 726 分类型也逐项相同），**只有 `calls` 差 13 条**（303 vs 316，+4.3%）。这精确证实了 `provenance.json` → `corpus.identical_to` 的说法，并把差异定位到调用解析这一个函数上。

**再顺带一个真实缺陷**：`_build_symbols`（`stages/graph.py:715-745`）按 qualified_name 去重、**保留第一条**。744 → 724，丢掉 20 条，来自 9 个重复名，**全部是 `@overload` 存根**：

```
src.requests.utils.iter_slices                x3 → 行 614 / 618 / 621
src.requests.models.Response.iter_content     x3 → 行 907 / 911 / 914
src.requests.auth.HTTPBasicAuth.__init__      x3 → 行 92 / 94 / 96   （另 6 个略）
```

库里验证：`iter_slices` 的 symbol line = 614，chunk 614–616，内容是 `def iter_slices(string: bytes, …) -> Generator[bytes, …]: ...`。所以 `find_definition("iter_slices")` 指向一个 3 行类型存根，inspector 打开也是存根，**所有指向这 9 个符号的调用边都落在存根上**。影响 9 个符号 / 20 个 chunk（726 的 2.8%）。`_symbols_for_file`（`:142-191`）不看 decorator，**无兜底**。

**(b) 726 chunks 是否覆盖 33 题的全部 gold chunk？**

**是，完全覆盖，recall 的数学天花板是 1.0。**逐项查库：

| 检查 | 结果 |
|---|---|
| 33 题全部有非空 `gt_chunk_ids` | ✅（若有空集，`recall_at_k` 会因 `retrieval.py:16-17` 返回 vacuous 1.0） |
| 声明的 `gt_targets` 数 vs 解析出的 chunk 数 | **逐题相等，0 题塌缩** |
| 去重后 gold chunk 总数 | **62** |
| 62 个是否都在索引里 | **62/62** ✅ |
| 零向量或 NULL 向量 | **0** ✅ |
| 落在 test 路径（会被 `_take` 过滤） | **0** ✅ |
| chunk_type | method 28 / function 21 / class 13（**无 module_doc**） |
| 行数 min/均值/max | **2 / 44 / 453** |
| ≤5 行 | **8 条**：7 个 `exceptions.py` 异常类 + `utils.guess_filename` |

另外 `resolve.py:99-103` 在任何锚点解析不到时直接 raise，所以「答案不在索引里」**不可能静默通过**——评测会崩，不会给出一个偏低但看似正常的 recall。

**但真正的天花板不在索引，在计分规则。** v2 把候选集合定义为 `min(|已验证证据|, 5)`，当 B4 引用的已验证 chunk 少于该题 gold 数时，recall **数学上就到不了 1.0**。repeat-1 的 B4 有 **9/33 题**存在这个上限：

| 题 | `\|scored\|` | `\|gt\|` | recall 上限 | 实际 |
|---|---|---|---|---|
| q-006 (L2) | 2 | 3 | 0.67 | 0.33 |
| q-017 (L2) | 2 | 3 | 0.67 | **0.67 ← 顶到上限** |
| q-019 (L2) | 2 | 4 | 0.50 | 0.25 |
| q-023 (L2) | 2 | 5 | **0.40** | **0.40 ← 顶到上限** |
| q-028 (L3) | 2 | 5 | **0.40** | 0.20 |
| q-029 (L3) | 4 | 5 | 0.80 | 0.60 |
| q-030 (L3) | 3 | 5 | 0.60 | **0.60 ← 顶到上限** |
| q-032 (L3) | 4 | 5 | 0.80 | 0.60 |
| q-033 (L3) | 4 | 5 | 0.80 | 0.40 |

**其中 3 题的实际 recall 已等于上限**——它们不是没检索到，是**没被允许再多引用一条**。这份评测测的不是"检索能否找到"，而是"**答案最终敢引用什么**"。

### 4.9 不可引用清单

| # | 数值 / 说法 | 为什么不可引用 |
|---|---|---|
| 1 | **B0 的 chunk 级 `recall/mrr/ndcg = 0.0`** | **结构性 0，不是成绩。** GitHub code search 返回路径不返回行号，产生不了 chunk id。说"B0 得 0 分"是把工具的输出粒度当成能力 |
| 2 | **「repeat 3 单独返回 supported」** | **挑有利重复。** 三次是 +0.0376/+0.0057/+0.0884，第 3 次是分布上端。判定口径是三次按题平均后再聚合（`run.py:271-282`），单次结论无决策地位。只能作为"这个 margin 不稳定"的**证据的一部分**出现 |
| 3 | **v1 协议下的四个 margin** | **被自己废弃的协议。** 它对 B4 用 final evidence、对 B2/B3 用 top-k，不对称。这组数**只能用于说明"协议改动的方向对自己不利"**，不能作为成绩，也不能说"其实我过了" |
| 4 | **「调用图有 473 条边」** | 473 是四种边之和，调用边 303。这句话本身是错的 |
| 5 | **「12.1% 的解析率」单独出现** | 不带分母定义无法判断高低。必须同时说明分母是 2615 个调用点、且 1076 个未解析属于明确放弃的能力 |
| 6 | **`pairwise_win_rate`** | 产物里全是 `null`。`StubJudge` 从未被实例化，`judge_model` 被读取零次。答案质量**未测量** |
| 7 | **`index_runs` 表的任何字段** | 表、触发器、索引都存在，**代码里没有任何写入方**。行不存在，字段值不存在 |
| 8 | **`chunks.tsv` / GIN 全文检索** | 列和索引存在，**全仓无写入点**，永远 NULL。任何"用了 Postgres 全文检索"的说法都是假的 |
| 9 | **`.env` 里的任何值单独引用** | `.env` 不入库，`.env.example` 全是 `stub`。运行值只能通过 `provenance.json` 引用 |
| 10 | **新集合下的 `4/3/5`（不说明来源时）** | 不是任何已提交字段的值，是重算出来的。必须说"重算" |
| 11 | **「前端 71 个测试」** | 实跑是 73。CLAUDE.md 的数字过时 |
| 12 | **B3.5 的任何数字作为"成绩"** | 它是诊断臂，代码层面被排除在决策外（`run.py:599-601`，测试 `test_run.py:686`）。当第五个 baseline 报就是改判定规则 |
| 13 | **`eval-suite/`、`eval-smoke/`、`b4-variance/`、`eval-real*/` 里的任何数字** | `results/README.md` 逐条标了 superseded / not a result / not a verdict。`b4-variance` 的九次单臂运行**不携带任何 H1 判定** |
| 14 | **「已证明 graph_reverse 没有偏置」** | 我测的是"指标上没兑现"。偏置的形式是**题集里缺什么**，用题集自身的指标测不出来。说成"证明无偏"会在追问第二层就崩 |
| 15 | **「B4 的 recall 是 0.638」** | 在 v2 口径下它等于 `final_evidence_recall_at_k`，测的是"答案引用了多少 gold"不是"检索找到了多少"。B4 的检索侧 `candidate_recall_at_k` 是 0.560，**和 B3/B3.5 完全相同**。混着说会被抓到 |
| 16 | **「三次重复所以更可信」** | 3 次只能说明方差存在，给不出置信区间。`limitations[1]` 自己写了：要解决 0.0061 这个量级需要**约 100 次重复** |
| 17 | **任何跨语言能力的说法** | 解析器是 stdlib `ast`，扫的是 `*.py`。**只支持 Python** |
| 18 | **「多轮对话 / 中文问答 / KaTeX 已被评测验证」** | `results/README.md` 明说这次运行不评测这三项（题集是英文、单轮、非数学）。它们只有单元测试和冒烟覆盖 |

### 4.10 主动交代清单

按「被对方问出来的杀伤力」从高到低。开口方式 ≤20 字。

| # | 事实 | 开口方式 | 不先说会怎样 |
|---|---|---|---|
| 1 | H1 判定是 `unsupported` | **「先说结论：主假设没通过。」** | 对方自己翻到 `h1_report.json`，之后所有陈述都被重新审视 |
| 2 | 单一语料、33 题 | **「一个仓库 33 道题，不外推。」** | 被问"换个 repo 呢"时才承认，显得是被逼出来的 |
| 3 | L2 那 0.006 小于噪声 | **「那 0.006 的差额小于噪声。」** | 若先说"只差一点点就过了"，会被追问方差，然后暴露极差 0.083 |
| 4 | 协议改过且改完结论变差 | **「我换过计分口径，换完就没过了。」** | 被发现有 v1/v2 两套协议时，"改协议"天然像 p-hacking，先说才能证明方向相反 |
| 5 | 去掉 groundedness 等于降门槛 | **「我删了一项指标，等于降门槛。」** | `run.py:648-665` 自己写着 "It is a lowered bar"，被读到而没先说等于隐瞒 |
| 6 | graph_reverse 的构造偏置 | **「17 道题是从我自己的图反推的。」** | 被问"题目哪来的"时才说，等于承认藏了一个已知偏置 |
| 7 | 调用图贡献很小 | **「调用图只值 +0.022，循环值六倍。」** | 项目卖点是"调用图增强"，让对方自己发现主要贡献不是图，叙事整个塌 |
| 8 | judge 没接 | **「答案质量我没测，只测了取证。」** | 被问"答得好不好"时无话可说 |
| 9 | 记录的运行跑在旧图上 | **「跑评测那版图比现在少 13 条边。」** | 对方若自己重索引复现，数字对不上 |
| 10 | taxonomy × source 混淆 | **「L3 和反推题这两类分不开。」** | 这条是我自己刚发现并补进 `provenance.json` 的——被独立发现杀伤力最大 |
| 11 | `tsv`/GIN 是死列 | **「建了全文索引但没接线。」** | 被读 migration 的人发现"建了不用"，会怀疑其他 schema 也是装饰 |
| 12 | `@overload` 让 9 个符号指向存根 | **「有 9 个符号指到类型存根了。」** | 现场演示时点开 `iter_slices` 看到 3 行 `...`，比自己说出来难看得多 |
| 13 | `index_runs` 建了没人写 | **「溯源表建好了，还没接。」** | 同上 |
| 14 | Phase 4 连带删掉了 a11y live region | **「删旧页面时把 live region 一起删了。」** | 被问 a11y 时，说"没做"比说"删了一个已修好的"更糟——后者带教训 |
| 15 | agent 的 Redis 读写没兜异常 | **「工具缓存那处我没兜 Redis 异常。」** | 深读代码会发现"其他地方都兜了唯独这里没兜"的不一致 |

---

## 5. 面试产出

### 5.1 设计决策表

| # | 决策 | 第一性原理 | 替代方案 | 放弃它的具体原因 | 代价 |
|---|---|---|---|---|---|
| 1 | **加权 RRF（K=60，dense:sparse = 2:1）** 而非分数归一化后相加 | BM25 分数无界、依赖语料的 idf 与文档长度分布；余弦相似度有界且分布集中。两者**不同量纲也不同分布族**。任何归一化都要先假定一个分布形状，而这个假定会随查询漂移。**名次是两个排序器之间唯一不需要分布假设就可比的量** | min-max 归一化后加权求和 / z-score / learning-to-rank | min-max 的分母是本次查询的 `max−min`：若稀疏侧只有 2 个非零结果，第 2 名会被归一化成 0，等于丢弃；z-score 假定近正态而 BM25 分数重尾；LTR 要训练数据，我只有 33 题，拟合出的权重就是过拟合到评测集的超参——正是 `testpaths.py:14-17` 以同样理由拒绝"测试文件权重 0.7"的那类东西 | 丢掉幅度信息：第 1 名强 10 倍还是强 1%，RRF 里一样。且引入两个未经系统搜索的超参（K=60、2:1），只能用两个方向相反的测试钉住（`test_internal_routes.py:444` 与 `:465`） |
| 2 | **稀疏侧走应用层 Okapi BM25**，不用 `tsv`+GIN | 要让 B1 成为**可复现的基线**，就必须能在产物里声明确切的 `k1/b/idf 公式/tokenizer`。Postgres 的 `ts_rank` **不是 BM25**——不做文档长度归一化，idf 也不是 Okapi 形式 | `tsv`+`ts_rank_cd`+GIN；ParadeDB/pg_search；Elasticsearch | 要在 SQL 里做出真 BM25 得自己算 idf 和 avgdl，那时"省一层代码"的好处没了，只剩参数藏在 SQL 里、无法单测、无法写进 `run_config.json`；且 `tokenize_code`（`bm25.py:24-45`）要同时产出 `httpbasicauth` 紧凑形式和 `http/basic/auth` 分段形式，Postgres 默认 parser 做不到 | 每个 `(repo_id, index_revision)` 首查要把全仓 chunk 拉进进程建索引（`retrieval/bm25.py:66-96`），LRU 只有 8 个 repo（`:16`）。726 chunk 无所谓，10 万 chunk 就是内存和冷启动问题——**明确的规模上限** |
| 2b | **`chunks.tsv` + GIN 保留但未接线** | — | — | — | **这不是设计，是债。**对外说法：「schema 里有一个我没用上的全文索引，是先建 schema、后来发现 `ts_rank` 不是 BM25 才换掉的遗留。它现在每次 INSERT 都在维护一个永远为 NULL 的索引，代价很小但不该留，下一次 migration 应该删。」**绝不能说成"我们也支持数据库全文检索"** |
| 3 | **所有 `citation` 在图跑完后一次补发**，不流式盖章 | 一条 citation 是一个**断言**：这个位置存在于索引里。断言只能在验证之后发。而验证发生在 `groundedness_node`，它必须等完整答案文本存在才能从中抽引用——**"流式盖章"在时序上不可能** | 检索到 chunk 就发 `verified:false` 的 citation，settle 时覆盖 | 那会让流式阶段就出现引用 chip，而此时正文尚未被抹除。`Turn.tsx:33-39`：**一个被打断的 turn 完全可能已握有若干条逐条已验证的 citation，而它的正文从未经过抹除**——绑定它们等于给没挣到保证的散文盖章 | 流式阶段看不到引用；settle 那一刻有视觉跳变（惰性 `CodeChip` → 可点 `CitationChip`）。刻意的两阶段，`Turn.test.tsx` 的 "two-phase honesty" 钉住 |
| 4 | **`interrupted` 是独立第四态** | `done` = 验证跑过且通过；`error` = 某步失败；`interrupted` = **验证从未运行**。第三种与前两种差在种类不是程度——「没检查过」和「检查了没通过」是不同的主张 | 归入 error（三态）；归入 done 并展示 partial（两态） | 归入 error 会把"用户主动停止"显示成故障；归入 done 会把一段从未被抹除的草稿呈现为权威答案 | UI 多一个分支、`useThread` 多一个 `stopped` 标记（`useThread.ts:99-101`）、Trace 多一种中性色（`Trace.tsx:16` 注释明写"**刻意不用 amber，因为 amber 表示已检查未通过**"）。三处组件都要处理 |
| 5 | **规划器是规则表，不是 LLM** | 这个项目要测的是"多步取证有没有价值"。规划器若是 LLM，B3.5 与 B4 的差异里就混进"LLM 这次碰巧选了什么工具"的方差——而**光是合成的方差就让 L2 的 margin 在三次重复间摆了 0.083**。再叠一层随机决策，消融就无法归因 | LLM function calling；ReAct prompt | 见左；另外规则表可被单测穷举（`test_graph.py` 的 33 个用例里 12 个是路由测试），LLM 规划器不行 | **泛化差，且是真实产品缺陷不是学术取舍。**路由靠关键词表——`_needs_multihop` 17 个词（`graph.py:1087-1112`）、`_call_query_direction` 22 个标记（`:1312-1358`）。不含关键词的架构问题会在第一次检索后直接停，而且**外部无法区分"规划器认为没有下一步"和"规划器没看懂"** |
| 6 | **证据上下文预算 10，对所有 arm 相同** | 若 B4 能塞更多证据，那 B4 赢了也可能只是上下文更长。要让"调用图有没有用"有意义，graph 证据必须**在固定容量里挤掉检索证据**，而不是被追加 | 按 arm 给不同预算；不设预算 | B3 最多只有 5 个检索块，给它 15 无意义；给 B4 更大预算会让上下文长度成为混淆变量（`graph.py:429-431`） | B4 在证据多的题上会丢一部分 content——但**超预算条目 content 清空而 ID 保留**（`graph.py:483-488`），仍可引用可验证，只是不花上下文 |
| 7 | **groundedness 不进 composite** | 一个在所有 arm 上恒等于 1.000 的项，**区分度为零**，却把每个 margin 稀释 1/4。把它放进判据是用不区分的量稀释区分的量 | 保留四项；给三项加权 | 见左 | **这条在时序上洗不白**：改动发生在四次运行都没过四项门槛之后，且因被移除项恒为 1.0，去掉它等价于每个 margin 乘 4/3，即门槛从 0.050 降到 0.0375。`run.py:648-665` 自己写着 *"It is a lowered bar, honestly labelled."* 辩护只有三条：①在被用于判决的那次运行**之前**声明并提交；②四项口径同时发布在 `four_term`；③**两种口径都是 unsupported** |
| 8 | **证据排序特征刻意不含 origin 与 `graph_distance`** | 若排序里有"graph 来源加分"，那 B4 赢就是因为我给它加了分。**要测一个东西有没有用，就不能在打分里假定它有用** | 给 graph 来源先验权重；把跳数作为特征 | `graph.py:451-454` 原文：*"A tunable 'prefer graph results' prior fitted on the evaluation set would be a hyper-parameter chosen to make the hypothesis pass."* | graph 证据必须在**同一条相关性尺度上**赢过检索证据。这直接解释了为什么六个 `GRAPH_TOOLS` 里有四个从未产出被引用的证据——**它们赢不过。这是我选择承受的负面结果** |
| 9 | **graph 证据先水合源码再统一排序** | 检索结果带代码、graph 结果只有 `file:line`，那 cross-encoder 比较的不是"哪个更相关"而是"哪个有东西可读"。这是**测量偏差**不是模型偏好 | 不水合直接排序；给 graph 结果补偿分 | 不水合会系统性低估 graph；补偿分是第 8 条禁止的先验 | 多一次 HTTP 往返（≤64 个 id，`graph.py:511`）；水合失败时该条 content 为空、排到未打分尾部（`:519-521`）——**降级方向是保守的** |
| 10 | **B3.5 是诊断臂，代码层面排除在判决外** | `B4−B3` 在 graph 或多步取证任一变动时都会动，单独说不出是哪个。`B4−B3.5` 固定 agent、只拿掉 graph，**那才是假设本身**。但把新臂加进判据 = 事后改判定规则 | 把 B3.5 提进 H1 判据 | `run.py:605-616` 原文：*"promoting an arm into the decision rule would be changing the pass criteria after the fact — the one thing the standing commitments forbid."* 由 `test_run.py:686` 钉住 | **这个项目最有价值的发现（graph +0.022 vs agent loop +0.147）只能作为 diagnostic 出现，不能改变 `unsupported`。我接受这个代价，因为反过来更糟** |

### 5.2 追问树

每条回答要点后的 `【§x】` 指向 §4 台账分区。

#### (a) 调用图贡献这么小，项目前提是不是错的

| 层 | 追问 | 回答要点 |
|---|---|---|
| 1 | 既然图只值 +0.022，你这个项目的前提不就垮了？ | 前提部分垮了，**而且是我自己的消融把它测垮的**。原命题判 `unsupported`【§4.5】。但被验证的东西换了一个：agent 的多步取证在 L3 值 **+0.147**，是图的**六倍多**【§4.5，须带"诊断项不进决策"】。项目价值从"图有用"变成"**多步取证 + 程序化引用验证有用**"，而这个区分只有 B3.5 能给出 |
| 2 | 那你为什么不早点发现？消融是事后补的吗？ | B3.5 在 `uniform-v2` 那一轮**首次引入**，和 v2 协议同一批。此前 `B4−B3` 是唯一的量，它在 graph 或 agent 循环任一变动时都会动——**单独说不出是哪个**（`run.py:605-616`）。发现"图贡献小"就是引入 B3.5 的直接结果。我没有事后补，我是补了才看见 |
| 3 | 那你怎么保证 B3.5 真的只关掉了图？ | 靠一个共享 frozenset：`GRAPH_TOOLS` 六个工具（`graph_tools.py:58-67`），agent 侧 `state.py:57` 做禁用清单，评测侧 `run.py:506` 做 origin 计数。**这两处曾经不一致过**——旧集合含 `get_file_outline`，而 B3.5 保留该工具，于是"没有图的臂"被记了 **12 次图命中**、"有图的臂"记 14 次【§4.5，须带"被废弃的旧集合"】。**一个分不清有图和没图的度量不是偏高，是测错对象。**修好后新集合下 B3.5 是 **0/0/0**、B4 是 **4/3/5**【§4.5，须带"重算值"】，我按 `run.py:491-513` 从已提交字节重算过，逐位一致 |

#### (b) 17 道题是你自己从图反推的，凭什么可信

| 层 | 追问 | 回答要点 |
|---|---|---|
| 1 | 题目从你自己的图反推，那不就是自问自答？ | 有偏置，我记录了没纠正。形式很具体：**由自己产出的图反推的题集，不可能包含这个图漏掉的流**。已知盲区（无类型推断、未解析的继承 `self.method()`）按构造就不在题里【§4.4】。这写在题集 README、写在 commit message、写在测试 docstring（`test_questions_dataset.py:26-29`） |
| 2 | 记录了不等于没影响。你怎么知道它没让 B4 赢？ | 我测过，指标上没兑现。按 `source` 切开：graph 的孤立贡献在 `graph_reverse` 题上是 **+0.018**，manual 题上是 **+0.028**——**更小不是更大**【§4.5】。引用了至少一条 graph 来源证据的题目比例是 **9/16 vs 10/17**，几乎相同【§4.5】 |
| 3 | 那你是不是可以说偏置不存在了？ | **不能，这正是边界。**我测的是"已有的题偏不偏向图"，测不了"图漏掉的流"——**它们不在样本里**。用题集自身的指标证明题集无偏，逻辑上不成立【§4.9 第 14 条】。而且还有一层我刚发现并补进 `provenance.json` 的混淆：**5 道 L1 全是 manual、17 道 graph_reverse 全是 L2/L3，且 gold 集合大一倍**（4.29/2.94 vs 2.12/1.38）【§4.4】——所以「B4 在 L3 领先」和「B4 在反推题上领先」这份数据分不开 |

#### (c) v2 计分口径怎么定的，是不是挑了好看的；那你又为什么删掉 groundedness 项

| 层 | 追问 | 回答要点 |
|---|---|---|
| 1 | 你换过计分协议？换的方向对你有利吗？ | **相反。**v1 对 B4 用已验证证据、对 B2/B3 用检索 top-k，不对称。v2 让四个 agent 臂用同一条规则（`run.py:83` + `AGENT_BASELINES`）。在这份数据上：**v1 会给出 `supported`（L2 +0.0822、L3 +0.1473），v2 给出 `unsupported`（L2 +0.0439）**【§4.9 第 3 条：v1 的数只能说明方向不能当成绩】。**协议改动让我自己的结论从过变成没过** |
| 2 | 但你又删了 groundedness 项，那不就是降门槛？ | **是降门槛，我不打算换说法。**被删项在所有 arm 上恒为 1.000，删掉等价于每个 margin 乘 4/3，门槛从 0.050 降到 0.0375【§4.5，须带"两种口径都是 unsupported"】。`run.py:648-665` 原文写着 *"It is a lowered bar, honestly labelled; calling it anything else would be false."* |
| 3 | 那你凭什么说这不是 p-hacking？ | 三条，都可核对：**①**它在被用于判决的那次运行**之前**声明并提交（`provenance.json.git.commit_note`）；**②**四项口径的完整结果**同时发布**在 `h1_report.json` 每一行的 `four_term` 里，不需重算就能读；**③两种口径都返回 `unsupported`**，所以这次改动没有改变这次的结论。我给不出第四条——时序上它确实发生在四次失败之后，这一点我不辩解 |

#### (d) 12% 解析率的调用图有什么实用价值

| 层 | 追问 | 回答要点 |
|---|---|---|
| 1 | 2615 个调用点只解析出 316 个，这图能干嘛？ | 它是**高精度低召回的静态近似**，不是完整调用图。12% 的分母是 worker 实际遍历到的调用点【§4.1，须带分母定义】，未解析的最大一类是 1076 个 `obj.X()`——**解决它需要类型推断，而这是明确声明放弃的能力**（`stages/graph.py:414-419`） |
| 2 | 那漏掉的 88% 不会给用户错误答案吗？ | 漏是安全的，**错才危险**。设计上宁可不建边：`_resolve_call_target` 每个分支都要求结果落在已知符号集合里，否则返回 `None`（`graph.py:302,343,346`）。而且未解析的调用**不是被丢弃，是被显式暴露**——API 层的 `source_calls` 把它们连同 UNRESOLVED 标记给 LLM（`internal.py:792-827`），系统 prompt 有硬规则禁止把源码里可见的调用表达式说成已解析的边（`llm.py:54-60`），测试钉住（`test_synthesis.py:141`） |
| 3 | 那你做过什么让这 12% 变高？ | 一件事，可量化：`_resolve_self_attribute` 的继承链 BFS（`graph.py:363-402`）。没有它，`requests` 里整个重定向机制对图不可见——`resolve_redirects` 定义在 `SessionRedirectMixin` 上，`Session.send` 通过 `self.` 调用它。还有 `_local_variable_types`（`:405-445`）只认字面构造，重复赋值直接丢弃不猜（测试 `test_graph_stage.py:401`）。**这两项当前代码会让调用边从 303 涨到 316（+4.3%），但需要重索引才生效**【§4.1，须带"库里是 303"】 |

#### (e) 单仓库 33 题能支撑什么结论

| 层 | 追问 | 回答要点 |
|---|---|---|
| 1 | 33 题、一个仓库，你能得出什么结论？ | 只有一条：**在这个语料上，H1 判 `unsupported`**【§4.5】。`provenance.json.limitations` 原文就是 *"One repository, 33 questions. Nothing here generalises."* |
| 2 | 那 L3 上 +0.169 算不算数？ | 算，但只在这个语料上算。它三次重复**各自单独都过**（+0.132/+0.175/+0.201）【§4.5】。L2 那条不算——三次是 +0.038/+0.006/+0.088，**极差 0.083 比 0.05 的门槛本身还宽**【§4.5】 |
| 3 | 那要多少题才够？ | 有数：L2 差额 0.0061 对应的重复间标准差 0.034（总体口径，样本口径 0.042）【§4.5，须带口径】，`limitations[1]` 算过，在这个题量下解决这个量级需要**约 100 次重复**。所以**正确做法不是多跑重复，是加 L2 题或换第二个语料**。题集 README 写了具体目标：`L3 ≈ 22` 才能让单题权重降到 0.05 门槛之下——现在 `L3 = 12`，**一道题就能把该层 composite 挪动 8.3%** |

#### (f) 为什么 recall 打的是"答案引用了什么"而不是"检索找到了什么"

| 层 | 追问 | 回答要点 |
|---|---|---|
| 1 | 你的 recall 测的不是检索能力？ | 不是，v2 下测的是**答案最终敢引用什么**。检索侧另有字段：B3/B3.5/B4 的 `candidate_recall_at_k` 是 **0.560，三者完全相同**——因为它们共用同一条 hybrid 检索路径【§4.9 第 15 条：两个不能混着说】 |
| 2 | 为什么这么定？这不是给自己挖坑吗？ | 是挖了坑，但挖对了地方。**检索找到但答案没引用，对用户等于没找到。**而且这条口径让"引用必须通过索引验证"进入指标——没验证过就不计分（`run.py:481-488`）。坑很具体：repeat-1 里 **9/33 道题 B4 的 recall 天花板本来就 <1.0**【§4.5 / §4.8b】 |
| 3 | 有没有具体例子？ | q-009：B4 产出 **6 条已验证证据，第 6 条被 `[:5]` 切掉，而那条正是 gold**。recall = 2/3 = 0.667 而不是 1.0【§4.5，须带"三条都找到了、都验证了、都写进答案了，指标只认前五条"】。这道题的三个指标我都手算复现过——`DCG = 1/log₂2 + 1/log₂6 = 1.3869`，`IDCG = 1+1/log₂3+1/log₂4 = 2.1309`，`nDCG = 0.650821`，与产物逐位一致 |

### 5.3 局限性口径（可直接说出口的措辞）

| 局限 | 措辞 |
|---|---|
| **H1 判定** | 「主假设判 `unsupported`。四个比较过了三个：L3 对两个对手都过（+0.247 / +0.169），L2 对扁平 RAG 过（+0.136），对 hybrid+rerank 没过。我不撤回也不软化这个结论——它是我自己的执行规则算出来的。」 |
| **L2 不可判定** | 「L2 那条**不是差一点，是测不出来**。三次相同配置跑出 +0.038 / +0.006 / +0.088，极差 0.083 比 0.05 的门槛本身还宽。在这个题量下，我没有能力把这个尺度的效应和噪声分开——所以我不会说'差 0.006 就过了'，那是在拿噪声当结论。」 |
| **两次协议改动方向相反** | 「我改过两次评测口径，方向是反的。计分协议从 v1 改到 v2，让四个 agent 臂用同一条规则——**改完我自己的结论从 supported 变成 unsupported**。同一批改动里我把 groundedness 从 composite 拿掉了，那**确实是降门槛**，等价于把 0.050 降到 0.0375。我把两种口径都发出来了，两种都是 unsupported。」 |
| **taxonomy × source 混淆** | 「有一处混淆是我这周才发现并补进 `provenance.json` 的：5 道 L1 全是人工题，17 道反推题全是 L2/L3 且 gold 集合大一倍。所以『B4 在 L3 领先』和『B4 在反推题上领先』**这份数据分不开**。我测过混淆的方向不利于 B4，但那不等于排除了它。」 |
| **记录的运行跑在旧调用图上** | 「跑评测的那份索引比现在的代码**少 13 条调用边**（303 vs 316，−4.3%）。改进的调用解析已提交但没生效——它需要重索引，而中途重索引会让语料在几次对比之间移动。我把这个差异定位到了具体函数，不是模糊的『代码变过』。」 |
| **judge 未接** | 「**答案质量我没有测量。**judge 还是 stub，`pairwise_win_rate` 在产物里全是 `null`。我测的是检索和引用验证——能不能找到正确的代码、引用是不是真的存在。答得好不好、解释得清不清楚，这套评测说不了。」 |
| **`@overload` 存根** | 「符号表按 qualified name 去重时保留第一条，而 `@overload` 存根排在真实现前面。结果是 9 个符号、20 个 chunk 指向的是类型存根不是实现——比如 `iter_slices` 点开会看到三行 `...`。占 chunk 总数 2.8%，修法是建符号时跳过带 `@overload` 装饰器的定义。」 |
| **`tsv` 死列** | 「schema 里有一个我没接线的全文索引。是先建 schema、后来发现 `ts_rank` 不是 BM25 才换成应用层实现的遗留。它现在每次 INSERT 都在维护一个永远为 NULL 的 GIN 索引——代价很小但不该留，下一次 migration 应该删掉。」 |
| **`index_runs` 未接线** | 「索引溯源表建好了，连 append-only 触发器都写了，**但没有代码写它**。所以现在没有任何东西能证明『某次查询跑的索引，就是某一行 `repos` 描述的那个』——`commit_sha` 只有一半信息。这是 Outstanding Work 里的一条，`db/models.py:7-11` 自己记着。」 |

### 5.4 三个版本讲述

> 数字只用 §4 台账里的白名单，且每个数字必须带上它那句「必须同时说的话」。

#### 30 秒

> Dcode 是一个代码理解系统：索引一个 Python 仓库，然后用一个有界的 agent 回答关于它的问题，**每一条引用都要通过索引验证，验证不过就从答案里抹掉**。
>
> 我原本要证的是"调用图增强的检索优于扁平向量 RAG"。**这个假设判了 `unsupported`**——四个比较过了三个。
>
> 更值得说的是反转：**我自己造了一个消融臂，把调用图关掉、其他全不变。结果调用图只值 +0.022，而 agent 的多步取证值 +0.147，是它的六倍**。也就是说，**消融否掉了我这个项目的招牌功能**，真正起作用的是多步取证加程序化引用验证。这个消融臂在代码层面被明确排除在判决之外——把它加进判据就是事后改规则。

#### 2 分钟

> **它做什么。** 提交一个 Git 仓库，worker 走一条六态状态机：clone → AST 解析 → 按语法边界分块 → 向量化 → 建调用图。然后在 workbench 里提问，agent 边跑边把 thought / tool_call / tool_result / partial_answer 通过 SSE 推给前端，最后统一补发引用和终答。
>
> **架构上有两件事我会展开讲。** 一是**单一 API 缝**：SPA 只跟网关说话，agent 通过 HTTP 回打网关的内部检索口——**四个应用包之间零 Python import**，评测 harness 也一样，它只依赖 `httpx` 和共享 schema，**结构上无法 import 被测系统**。二是**诚实性契约**：引用只有在 groundedness 节点验证之后才发；一个流断了但没收到 `final_answer` 的 turn 是**第四种状态 `interrupted`**，它的草稿会被降格显示、引用一律不绑定——因为「没检查过」和「检查了没通过」是不同的主张。
>
> **评测。** 五级 baseline，语料是 `psf/requests`，**726 chunk / 473 条边（四种边之和，调用边只有 303）**，33 道题，跑三次取平均。真实模型：Jina v2-base-code 768 维、BGE reranker v2-m3、gpt-4o-mini 合成；**judge 还是 stub，所以答案质量我没有测量**。
>
> **结论是 `unsupported`**，L2 对 hybrid+rerank 那一条没过。但那条**不是差一点，是测不出来**——三次跑出 +0.038 / +0.006 / +0.088，极差 0.083 比 0.05 的门槛本身还宽。
>
> **真正的发现来自我加的第五个臂 B3.5**：它是 B4 关掉调用图和引用工具、其他完全相同。`B4 − B3.5` 是调用图的孤立贡献 **+0.022 / +0.023**，`B3.5 − B3` 是多步取证的贡献，在 L3 上是 **+0.147**。**六倍。**所以这个项目验证的不是"调用图有用"，而是"**多步取证 + 程序化引用验证有用**"。B3.5 在代码里被硬性排除在 H1 判据之外，因为把新臂加进判据就是事后改判定规则。

#### 8 分钟深挖

> **一、问题与形态。**（同 2 分钟版前两段，展开索引链路的六态状态机与双写：Postgres 是持久真相、Redis `job:{repo_id}` 是给轮询的细粒度快照；以及查询链路的后台 task 模型——响应体是一个 `asyncio.Queue`，图在另一个 task 里跑，所以事件能边跑边推。）
>
> **二、检索。** 三条路：稀疏是应用层的 Okapi BM25（k1=1.2 / b=0.75，参数写进 `run_config.json` 以便 B1 可复现），稠密是 pgvector + HNSW 余弦，两路各取 50 后做**加权 RRF**——K=60、dense:sparse = 2:1。为什么是 RRF 而不是归一化相加：BM25 分数无界重尾、余弦有界集中，**名次是两者之间唯一不需要分布假设就可比的量**。权重非等权是因为等权时纯稠密的 nDCG 会反超混合，两个方向的测试各钉一个。融合后送 cross-encoder 重排前 16 条，最后取 5，并在**排序之后**过滤测试文件——过滤放在排序后，候选池和融合算术不受影响。
>
> 顺带一个债：schema 里有 `chunks.tsv` 和一个 GIN 索引，**没有任何代码写它**。是先建 schema、后来发现 `ts_rank` 不是 BM25 才换掉的遗留，下一次 migration 该删。
>
> **三、agent。** LangGraph 五节点：contextualize → plan → tool_call ⇄ plan → synthesize → groundedness_check。**规划器是规则表不是 LLM**——因为要测的就是多步取证的价值，规划器若随机，消融就无法归因。11 个工具，步数上限 14（从 8 提上来的，因为 B4 把 8 跑满了，走到上限是截断假象不是策略）。工具失败是**降级**（记 error 转合成，答案头部加故障提示），基础设施失败是**终止**（发 error 事件，不给答案）——分界画在 `_record_tool_failure` 上。
>
> **四、诚实性。** 两条重点。一是**引用验证**：LLM 只能引用服务端发的 `[C1]` 这类请求内 ID，任何不在目录里的 ID 直接判失败并从正文抹除；显式的 `file.py:42` 仍会独立验证。分数是**抹除前**的比例，所以大量抹除的答案仍然低分。二是**证据排序刻意不含 origin 和跳数**——因为要测图有没有用，就不能在打分里假定它有用。代价我认：六个图工具里有四个从未产出被引用的证据，**它们赢不过检索结果**。
>
> **五、我为什么造 B3.5，以及它测出了什么。** `B4 − B3` 在图或多步取证任一变动时都会动，单独说不出是哪个。B3.5 固定 agent、只拿掉图工具，于是差分可以分解。结果：图 +0.022 / +0.023，agent 循环在 L3 +0.147。**做这个消融的直接后果是我自己项目的核心卖点被降级了。**而且它还暴露了一个更硬的问题：负责统计"图找到了多少 gold"的那个工具集合，此前包含 `get_file_outline`——而 B3.5 保留这个工具。于是"没有图的臂"被记了 12 次图命中，"有图的臂"记 14 次。**一个分不清有图和没图的度量不是偏高，是测错了对象。**修好后新集合下 B3.5 是 0/0/0、B4 是 4/3/5。我按 `run.py` 的逻辑从已提交字节重算过，逐位一致。
>
> **六、我没能力回答的问题，和下一步。**
>
> | 下一步 | 具体做什么 | 能回答哪个现在答不了的问题 |
> |---|---|---|
> | **重索引** | 用当前 worker 代码重跑 `psf/requests` 索引（调用边 303 → 316，+4.3%），然后重跑三次重复 | 「改进的继承链解析和局部类型解析，对 L2/L3 的 margin 有没有可测的影响」——现在**完全未知**，因为记录的运行跑在旧图上 |
> | **扩语料** | 接入已索引的 `encode/httpx`（1152 chunk / 963 边，库里已有），先给它写 20–30 道题 | 「L3 上 +0.169 是这个库的性质还是方法的性质」——现在只能说"在这个语料上" |
> | **拆 taxonomy × source 混淆** | 补 8–10 道 **manual 的 L3** 和 3–5 道 **graph_reverse 的 L1**，让两个维度不再共线 | 「B4 在 L3 领先，是因为它是架构题，还是因为它是反推题」——现在这份数据分不开 |
> | **接 judge** | 把 `metrics/judge.py` 的 `Judge` ABC 接到一个真实模型，跑 pairwise 与四轴 rubric | 「答案本身好不好」——现在**完全没测**，`pairwise_win_rate` 全是 null |
> | **补 L2 题量** | 把 `L3` 从 12 推到约 22（题集 README 已算过这个目标） | 「L2 那 0.006 的差额是真效应还是噪声」——现在需要约 100 次重复才能分开，正确解法是加题不是加重复 |
>
> 我会按这个顺序做，因为**重索引最便宜且当前结论直接依赖它**，而接 judge 最贵且不影响已有结论的有效性。

### 5.5 现场演示风险清单

| # | 风险 | 会怎么炸 | **预先声明的说法** |
|---|---|---|---|
| 1 | **`make up` 不启动两个 sidecar** | embedding/reranker 挂了 profile（`docker-compose.yml:132-133`、`:153-154`），API 健康但**每个查询都死在 embedding** | 「起服务是三条命令不是一条——两个模型 sidecar 跑在宿主机上，Docker 里跑会 OOM。我先起它们，等到 `Embedding model ready` 再起主栈。」 |
| 2 | **工具缓存 24h** | `tool:{tool}:{repo_id}:{args_hash}` TTL 24h（`settings.py:35`）。**换过 agent 代码但没 flush，会拿到旧代码产出的图结果** | 「我先 flush 一下 Redis。工具结果缓存 24 小时，如果我这两天改过 agent，不 flush 你看到的可能是旧代码的输出——之前有一次评测就是这么中途作废的。」 |
| 3 | **agent 源码烧在镜像里** | `docker compose restart agent` 跑的是旧代码；新的 `AgentMode` 字面量会被旧镜像回 `422` | 「agent 的代码在镜像里不是挂载的，改完必须 `up -d --build agent api`，restart 不管用。」 |
| 4 | **`EMBEDDING_DIM` 768 vs 代码默认 1024** | 维度在 `alembic upgrade` 那一刻烧进 `vector(N)`（`001_initial_schema.py:91`）。`make down-all` 删卷后若 `.env` 没设 768，会按 1024 重建，**旧索引全部失效** | 「这个库是 768 维建的，代码默认是 1024。**不要跑 `make down-all`**——它删卷，重建会按环境变量当时的值定维度，得整个重索引。」 |
| 5 | **点开 `iter_slices` 看到 `@overload` 存根** | 符号去重保留第一条，存根排在实现前面，inspector 显示 3 行 `... ` | 「如果点到 `iter_slices` 或 `Response.iter_content`，你会看到三行省略号——那是 `@overload` 类型存根。符号表去重时保留了第一条，而存根排在实现前面。9 个符号中招，修法是建符号时跳过带 `@overload` 装饰器的定义。」 |
| 6 | **首次索引在 embedding 阶段"卡住"** | Jina 在 CPU 上跑，726 chunk 分 182 批，进度条长时间停在 embedding | 「索引会在 embedding 那一步停很久，那是真在算不是挂了——CPU 上跑 Jina，几百个 chunk 要几分钟。」 |
| 7 | **BM25 首查冷启动** | 每个 `(repo_id, index_revision)` 首查要把全仓 chunk 拉进进程建索引（`retrieval/bm25.py:66-96`） | 「第一次查会慢一点，稀疏检索是应用层的，首查要建一次 BM25 索引，之后走进程内缓存。」 |
| 8 | **读屏听不到流式答案** | 全仓无 `aria-live` / `role="log"`（grep 0 命中）；`Turn.tsx:69-78` 与 `Trace.tsx:61-121` 都没有 | 「如果你开读屏，流式答案是听不到的——Phase 4 退役旧页面时把已经修好的 live region 一起删了（`09e2446` 加的，`7bc6abe` 删的）。修法是把 live region 放在**已 settle 的答案**上而不是流式预览上，否则每个 token 都播报是噪音。」 |
| 9 | **库里五行重复的 `psf/requests`** | `POST /repos` 的幂等修复不追溯清理历史行 | 「库里有五行 `psf/requests`，是幂等修复之前留下的，修复不追溯。评测用的是 `2543893e` 那一行。」 |
| 10 | **headless 截图不可用** | 沙箱里 headless Chrome 挂在 `http://` URL 上 | 「视觉的东西我只能请你自己在浏览器里看，我这边截不了图。」 |

---

## 附录 A：文档漂移清单

合并 §1–§3 全部候选条目。**"文档"包括 schema、注释、docstring 与函数命名**——它们同样是对读者的陈述。

| # | 文档位置 | 文档说法 | 代码实际 | 建议改法 |
|---|---|---|---|---|
| 1 | `infra/migrations/versions/001_initial_schema.py:92,101`；`packages/shared/src/dcode_shared/db/models.py:129` | 有 `chunks.tsv` 列与 `ix_chunks_tsv_gin` 全文索引 | **全仓无写入点**；`stages/embed.py:180-196` 构造 `DBChunk` 时列出 10 个字段不含 `tsv`；无触发器、无 generated column。稀疏检索完全在 `packages/shared/src/dcode_shared/bm25.py` | 新增一个 migration **删除 `tsv` 列与 GIN 索引**；若要保留，必须在 `models.py` 的模块 docstring 里写明"未接线，保留待评估" |
| 2 | `infra/migrations/versions/002_index_runs.py`、`003_nonzero_embedding_count.py` | `index_runs` 表 + append-only 触发器 + `repos.current_index_run_id` | **代码里没有任何写入方**（`db/models.py:7-11` 自己诚实记录了） | 要么在 `stages` 收尾处写入一行 `index_runs` 并更新指针，要么把这条从 schema 挪进 Outstanding Work 并加 migration 移除。**不要长期保留一个没人写的溯源表** |
| 3 | `CLAUDE.md` §4「71 frontend tests」 | 前端 71 个测试 | 实跑 **73 个 / 16 个文件**（`npm test -- --run`） | 改成 73，或改成"以 `npm test` 实跑为准"不写具体数 |
| 4 | `CLAUDE.md` §4 提到 `EMBEDDING_DIM` 迁移 | 提及但没说清绑定时刻 | `Vector(shared_settings.embedding_dim)` 在 **migration 执行那一刻**固化进 DDL（`001_initial_schema.py:91`），不是运行时读取 | 补一句"维度在 `alembic upgrade` 时刻烧进列定义，改维度必须重建库" |
| 5 | `apps/agent/src/dcode_agent/graph.py:815` 函数名 `_select_initial_tool` | 名字宣称它选"初始工具" | **从不用于选择初始工具**——初始工具在 `graph.py:800-809` 硬编码为 `search_code`；唯一调用点是 `:906` 的 follow-up 专用路由 | 重命名为 `_select_specialised_route`，或在 docstring 首行写明它只在 follow-up 阶段使用 |
| 6 | `apps/agent/src/dcode_agent/graph.py:548-557` `_allowed_citations` | 有 docstring，看起来是生产路径 | **生产代码零调用**，仅被 `apps/agent/tests/test_citable_tokens.py:102` 调用 | 删除，或移进测试辅助模块；保留则在 docstring 标注"仅测试使用" |
| 7 | `apps/agent/src/dcode_agent/graph.py:755-756` | `decide_after_plan` 的 `draft_answer is not None` 分支 | **当前图拓扑下不可达**：`draft_answer` 只在 `:239` 赋值，而 `synthesize → groundedness_check → END`（`:792-793`），`plan` 永不在其后被进入 | 加一行注释说明它是防御性分支，或删除 |
| 8 | `apps/agent/src/dcode_agent/graph.py:130,142` | 与其他服务一致地读写 Redis | **未兜 Redis 异常**——`_cache_get`/`_cache_set` 都在 `try`（`:132-139`）之外，Redis 故障会冒泡成 `error` 事件。worker（`pipeline.py:303`）与网关（`query.py:148,159`）都兜了 | 把两次缓存调用移进 `try`，或单独 `try/except RedisError` 并记日志——与另外两处保持一致 |
| 9 | `packages/shared/src/dcode_shared/settings.py:59`；`.env.example:74`；`docker-compose.yml:171` | 有 `judge_model` 配置项 | **全仓读取零次**；`apps/eval/src/dcode_eval/metrics/judge.py:39-46` 的 `StubJudge` **从未被实例化** | 保留（它标记了未来接线点），但在 `settings.py` 该行加注释"当前未被任何代码读取；judge 未接线" |
| 10 | `apps/api/src/dcode_api/settings.py:11`、`apps/worker/src/dcode_worker/settings.py:10` | 队列名 `dcode.index_jobs` | **两处各定义一份**，无共享常量。改一处会静默失联 | 移进 `packages/shared/src/dcode_shared/`，两边 import |
| 11 | `apps/frontend/tests/CitationChip.test.tsx`（"renders unverified chips as amber outline"） | UI 支持"未验证"引用态 | **实时 SSE 流里到不了**——服务端只发已验证 citation（`graph.py:727-738`；`groundedness.py:377,401`），`verified` 恒为 `true` | 在测试或组件 docstring 注明该状态目前只由 `SourceResponse` 语义驱动；或让服务端也发未验证 citation 并由前端渲染 amber |
| 12 | `results/eval-h1-repeat3-2026-07-31/provenance.json` → `corpus.edges: 473` | 读者普遍会理解成调用图规模 | 473 是四种边之和；`calls` 只有 **303**（`references 72 / imports 65 / inherits 33`） | 把 `edges` 拆成 `edges_total` 与 `edges_by_type` 对象；或在同一层加一个 `edges_note` |
| 13 | `provenance.json` → `corpus.identical_to` | 「改进的调用解析已提交但未生效」 | ✅ **属实且可量化**：当前代码会产出 **316** 条 calls，比库里多 13 条（+4.3%）；其余三种边逐项相同 | 把 "+13 / +4.3%" 写进该字段，让"未生效"从定性变定量 |
| 14 | `apps/eval/src/dcode_eval/questions/README.md:40-41`；commit `ae47419` message | graph_reverse「reverse-constructed from the indexed call relationships」 | **无生成代码**（全仓 grep 只命中读取方）；**走了哪些 `edge_type` 代码中未找到** | 补一个 `scripts/` 下的生成/复核脚本；或在 README 明写"人工构造，无脚本；`edge_type` 过滤条件未记录" |
| 15 | `results/eval-h1-repeat3-2026-07-31/repeat-*/**/per_question.jsonl` | — | 仍是旧字段名 `structural_evidence_chunk_ids` / `new_gt_hits_from_structural_evidence`；**顶层重聚合的 `B*/per_question.jsonl` 两套字段都没有**（`_mean_across_repeats` `run.py:337-375` 只搬运固定白名单） | 在 `results/README.md` 该目录行注明字段代次；并把 graph-evidence 字段加进 `_mean_across_repeats` 的搬运列表 |
| 16 | `packages/shared/src/dcode_shared/graph_tools.py:29-31` 的 `4 / 3 / 5` | 呈现为可从已提交字节核对 | ✅ 我按 `run.py:491-513` 重算，逐位一致——**但它是重算值，不是任何已提交字段** | 在该表上方加一行"（重算自本目录字节，非产物字段）" |
| 17 | `apps/worker/src/dcode_worker/stages/graph.py:142-191`、`:715-745` | 符号表按 qualified name 唯一 | **`@overload` 存根覆盖真实现**：744 → 724，丢 20 条、9 个重复名，保留的全是存根（库里验证：`iter_slices` symbol line = 614，chunk 614–616，内容是 `... `） | `_symbols_for_file` 跳过带 `@overload` 装饰器的定义；或 `_build_symbols` 改为"保留最后一条" |
| 18 | `apps/eval/src/dcode_eval/metrics/retrieval.py:16-17` vs `:38` | — | 空 `gt` 时 `recall_at_k` 返 **1.0**、`ndcg_at_k` 返 **0.0**——同一模块两种真空约定 | 统一（推荐都 raise 或都返回 `float('nan')` 并在聚合处剔除），并加测试 |
| 19 | `apps/eval/src/dcode_eval/metrics/retrieval.py:22-23` | docstring 写 "Mean Reciprocal Rank" | 实为**单题 RR**（均值在 `run.py:438`）；且**签名没有 `k`**，`:24` 遍历整个列表。当前无害因为调用点都已截断，但未来调用方传未截断列表会静默得到 MRR@∞ | 改名 `reciprocal_rank` 并加 `k` 参数（内部 `retrieved[:k]`） |
| 20 | `apps/agent/src/dcode_agent/groundedness.py:136` vs `:218` | — | 空引用时一条返 **1.0**、一条会 **ZeroDivisionError**（当前均因上游早返回而不可达） | 两处统一走 `_uncited_result()`，或都加同样的守卫 |
| 21 | `apps/api/src/dcode_api/routes/internal.py:57` vs `apps/agent/src/dcode_agent/graph.py:434` | 同名常量 `_RERANK_PASSAGE_CHARS` | **同名不同值**（256 / 1000），且 agent 侧不限制候选数 | 重命名以区分用途（如 `_API_RERANK_PASSAGE_CHARS` / `_EVIDENCE_RERANK_PASSAGE_CHARS`），并在各自处注明为什么不同 |
| 22 | `provenance.json` → `limitations` | 此前未记录 taxonomy × source 混淆 | ✅ **本轮已补入**（数组 index 8，带 `ADDED AFTER THE RUN` 前缀，说明是从同目录字节重算、无任何 baseline 重跑）。`make lint` 三段全绿 | 已修。下一次运行时把该条改写为随 harness 一起记录的常规条目 |
| 23 | `results/eval-h1-repeat3-2026-07-31/suite_summary.json` | — | **没有 `file_*` 指标**——该 run 提交于 `15:17:48`，而 file 级计分的 commit `57c9542` 是 `15:38:15`，晚 21 分钟。因此 `results/eval-b0-2026-07-31/metrics.json` 的 file 级 0.308 **在仓库里没有可比对象** | 在 `results/README.md` 的 B0 行注明"file 级指标只有 B0 有，H1 那次运行不含 file 级"；或重跑一次 H1 以补齐 |
| 24 | — | 统计 Python 代码量 | `find apps packages -name "*.py"` 若不排除 `node_modules`，会多算 16 个共 **1743** 行的 `.py`（10952 → 12695） | 任何 LOC 声明都要写清排除项 |
| 25 | `CLAUDE.md` §4「Known open regression — accessibility live regions」 | 说明缺失但**未给出处** | ✅ **本轮补齐**：加入者 commit `09e2446`（"a11y live regions … P3-10"），删除者 commit `7bc6abe`（"retire the pre-rebuild IA (Phase 4)"）；删前的两行是 `QueryPage.tsx:184` `aria-live="polite"` 与 `:234` `role="log" aria-live="polite"`。现存 `apps/frontend/src` 的 aria 只有 `aria-hidden`×28 / `aria-label`×6 / `aria-pressed`×2 / `aria-expanded`×1 | 把这两个 commit 与两行行号写进 `CLAUDE.md` 该段，让"已知回归"带出处；并把它讲成"退役界面时要 diff 它消费了什么能力"的实例 |

---

## 附录 B：本文档的复验方式

| 数字来源 | 复验命令 |
|---|---|
| commit / 文件历史 | `git log --format='%h %s' -10`、`git rev-parse <hash>`、`git show <c>^:<path>` |
| 测试数 | `uv run pytest --collect-only -q`、`cd apps/frontend && npm test -- --run` |
| 代码行数 | `find apps packages -name "*.py" -not -path "*/tests/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" \| xargs wc -l` |
| 索引规模 | `docker exec dcode-postgres-1 psql -U dcode -d dcode -c "SELECT edge_type, count(*) FROM edges WHERE repo_id='2543893e-0965-4be7-ac45-5a8e38600bc0' GROUP BY 1"` |
| 调用点 funnel | scratchpad `call_ratio.py`（复刻 `stages/graph.py:265-281`），输入是 `docker cp` 出来的 `414f051` 工作目录 |
| 评测数字 | 直接读 `results/eval-h1-repeat3-2026-07-31/` 下的 json；per-source 切分与 v1/v2 对比由 `per_question.jsonl` 现算 |
| 产物一致性 | `python3 scripts/sync_eval_artifacts.py --check`（已并入 `make lint`） |

**注意**：`provenance.json` **不是 harness 输出**——`apps/eval/src/dcode_eval/run.py` 的全部写入点只有 `run_config.json` / `per_question.jsonl` / `metrics.json` / `taxonomy_breakdown.json` / `suite_summary.json` / `h1_report.json`（`run.py:68,166,167,168,206,220,225,273,299,301,380,382,389`）。`scripts/sync_eval_artifacts.py` 只把它当只读输入，取用 `display`（`:189`）、`groundedness_guardrail`（`:190`）、`verdict_written_at`（`:196`）、`sparse_retrieval`（`:206`）四个 key，**从不读 `limitations`**。
