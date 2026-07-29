# Dcode 数据库参考 (Database Reference)

> ## 📁 已归档 — 中文文档快照，**非当前状态**
> 
> 中文文档已于 2026-07-29 停止维护（原因见 [README.md](README.md)）。**当前状态请看 `docs/en/`。**
> 本文可能与实现不一致，请勿据此判断项目现状。


> ⚠️ 交接快照，可能滞后于 `docs/en/`；以英文文档为准（en/ is the source of truth）。

本文档是 Dcode 持久层的权威参考：PostgreSQL schema（表、列、枚举、索引、约束）、
Redis 键空间、数据如何写入与读取，以及如何用 SQL 查看。它在
[`Technical_Design_ch.md` §3（数据模型）](Technical_Design_ch.md) 的基础上补充了
列级细节和一份可操作的 SQL 手册。

**代码中的真实来源：**

| 关注点 | 文件 |
|---|---|
| ORM 模型（表、列、关系） | `packages/shared/src/dcode_shared/db/models.py` |
| 枚举 / API 载荷结构 | `packages/shared/src/dcode_shared/schemas.py` |
| DDL、索引、迁移 | `infra/migrations/versions/001_initial_schema.py` |
| 异步 engine / session 工厂 | `packages/shared/src/dcode_shared/db/session.py` |
| Redis 键约定 | `packages/shared/src/dcode_shared/cache.py` |
| 检索 / 图谱 SQL | `apps/api/src/dcode_api/routes/internal.py` |
| 写入路径（索引） | `apps/worker/src/dcode_worker/stages/*` + `pipeline.py` |

---

## 1. 数据库里存的是什么

Dcode 把一个 Git 仓库索引成**两个互补的检索面**外加一张登记表：

- **登记表** —— `repos`：每个被提交的仓库一行，记录其索引状态。
- **语义面** —— `chunks`：AST 边界代码切片，每块携带一个稠密 `embedding` 向量
  （用于语义检索）和一个 `tsv` 全文列（保留字段，见 §8）。`/internal/search` 读它。
- **结构面** —— `symbols`（图节点）+ `edges`（图边）：一张静态的
  调用/导入/继承/引用图。图查询接口（`find_definition`、`find_references`、
  `get_dependencies`、`get_dependents`、`get_file_outline`）读它。

所有数据都**按 `repo_id` 多租户隔离**（NFR-3）：每个子表行都带着所属的
`repos.id`，所有查询都按它过滤。

### 存储拓扑

| 存储 | 角色 | 持久？ |
|---|---|---|
| **PostgreSQL 15 + pgvector** | `repos`、`chunks`、`symbols`、`edges` —— 向量与图同一实例 | 是（`postgres_data` 卷） |
| **Redis 7** | embedding 缓存、工具缓存、query-SSE 缓存、实时 job 状态快照 | 否（缓存，按键设 TTL） |
| **RabbitMQ** | 持久的索引任务队列（`dcode.index_jobs`）—— 传输，非存储 | 消息持久 |
| **仓库工作目录卷** | 磁盘上克隆的仓库源码（`/tmp/dcode-workdirs/{repo_id}`）—— 供 agent 的文件系统工具读取 | `repo_workdirs` 卷 |

把向量与图放在同一个 PostgreSQL 实例，让 Dcode 只有一个连接池、一个备份边界、
一个一致性模型（见 [`Technical_Design_ch.md`](Technical_Design_ch.md) 的关键设计决策）。

---

## 2. 实体模型

```text
repos (1) ─────────< (N) chunks
   │                        ▲
   │                        │ chunk_id (SET NULL)
   └───────< (N) symbols ───┘
                  │
                  │ source_id / target_id
                  ▼
               (N) edges        边: symbol ──edge_type──> symbol
```

- `repos 1─N chunks`（外键 `chunks.repo_id`，`ON DELETE CASCADE`）
- `repos 1─N symbols`（外键 `symbols.repo_id`，`ON DELETE CASCADE`）
- `symbols N─1 chunks`（外键 `symbols.chunk_id`，`ON DELETE SET NULL`）——
  一个符号可选地链接到包含其定义的 chunk。
- `edges` 连接两个 `symbols`（`source_id`、`target_id`，均 `ON DELETE CASCADE`）。

删除一行 `repos` 会级联删除其所有 `chunks`、`symbols`、`edges`。

---

## 3. 枚举类型

四个 PostgreSQL `ENUM` 类型支撑 schema，其字面值必须与 `schemas.py` 中的
`StrEnum` 一致。

| 枚举 | 取值 | 用于 |
|---|---|---|
| `repo_status` | `queued`、`cloning`、`parsing`、`embedding`、`graphing`、`ready`、`failed` | `repos.status` |
| `chunk_type` | `function`、`method`、`class`、`module_doc` | `chunks.chunk_type` |
| `symbol_kind` | `function`、`class`、`method`、`module` | `symbols.kind` |
| `edge_type` | `calls`、`imports`、`inherits`、`references` | `edges.edge_type` |

`repo_status` 沿流水线单调前进
（`queued → cloning → parsing → embedding → graphing → ready`），
只会横跳到 `failed`。另有一个应用层的 `StageState`
（`pending`/`in_progress`/`done`/`failed`）仅存在于 Redis job 快照与状态 API 中，
**不是**数据库列。

---

## 4. 表参考

### 4.1 `repos` —— 索引登记表

每个被提交的仓库一行，由 worker 在每次阶段转换时更新。

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | `UUID` | 否 | `uuid4()` | 主键；作为 `repo_id` 返回给客户端 |
| `url` | `TEXT` | 否 | — | Git URL（API 侧校验：禁 localhost/内网 IP） |
| `commit_sha` | `TEXT` | 是 | — | clone 解析出 `HEAD` 后写入 |
| `status` | `repo_status` | 否 | `queued` | 当前流水线状态 |
| `progress` | `INTEGER` | 否 | `0` | 0–100 |
| `error` | `TEXT` | 是 | — | `status = failed` 时的失败原因 |
| `created_at` | `TIMESTAMP` | 否 | `now()` | 由 DB 管理 |
| `updated_at` | `TIMESTAMP` | 否 | `now()`（更新时 `now()`） | 由 DB 管理 |

### 4.2 `chunks` —— 语义检索面

每行是一块 AST 边界代码切片：模块文档串、顶层函数、类，或方法。这是可检索的最小单元。

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | `UUID` | 否 | `uuid4()` | 主键 |
| `repo_id` | `UUID` | 否 | — | 外键 → `repos.id` `ON DELETE CASCADE` |
| `file_path` | `TEXT` | 否 | — | 仓库相对路径，如 `src/requests/auth.py` |
| `chunk_type` | `chunk_type` | 否 | — | `function`/`method`/`class`/`module_doc` |
| `parent_symbol` | `TEXT` | 是 | — | 方法的外层类名；否则 `NULL` |
| `symbol_name` | `TEXT` | 否 | — | 短名，如 `HTTPBasicAuth`、`send` |
| `signature` | `TEXT` | 是 | — | 用 `ast.unparse` 重建的完整 def/class 头（规范化为单行） |
| `start_line` | `INTEGER` | 否 | — | 1-based；不含装饰器行（用 `node.lineno`） |
| `end_line` | `INTEGER` | 否 | — | 1-based，闭区间 |
| `imports` | `JSONB` | 否 | `[]` | 模块级 import + 节点内部发现的 import |
| `content` | `TEXT` | 否 | — | 原样源码切片（上限 `max_chunk_chars`，默认 20000，超出加 `... [truncated]` 标记） |
| `embedding` | `VECTOR(N)` | 是 | — | 稠密向量；`N = EMBEDDING_DIM`，**迁移时固定**（见 §13/§17） |
| `tsv` | `TSVECTOR` | 是 | — | 全文列 —— **当前从未写入**（见 §8） |

### 4.3 `symbols` —— 图节点

每行是一个定义（模块、类、函数、方法）。它们是调用图的节点，也是
`find_definition` / `get_file_outline` 的目标。

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | `UUID` | 否 | `uuid4()` | 主键 |
| `repo_id` | `UUID` | 否 | — | 外键 → `repos.id` `ON DELETE CASCADE` |
| `qualified_name` | `TEXT` | 否 | — | 点分路径，如 `src.requests.auth.HTTPBasicAuth.__call__` |
| `kind` | `symbol_kind` | 否 | — | `function`/`class`/`method`/`module` |
| `file_path` | `TEXT` | 否 | — | 定义所在文件 |
| `line` | `INTEGER` | 否 | — | 定义行（`module` 符号用第 1 行） |
| `chunk_id` | `UUID` | 是 | — | 外键 → `chunks.id` `ON DELETE SET NULL`；把符号连回其代码块 |

`qualified_name` **在仓库内唯一**（`ix_symbols_repo_qname_unique`）。

### 4.4 `edges` —— 图边

每行是两个符号之间的一条有向关系。

| 列 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | `UUID` | 否 | `uuid4()` | 主键 |
| `repo_id` | `UUID` | 否 | — | 外键 → `repos.id` `ON DELETE CASCADE` |
| `source_id` | `UUID` | 否 | — | 外键 → `symbols.id` `ON DELETE CASCADE`（“从”符号） |
| `target_id` | `UUID` | 否 | — | 外键 → `symbols.id` `ON DELETE CASCADE`（“到”符号） |
| `edge_type` | `edge_type` | 否 | — | `calls`/`imports`/`inherits`/`references` |
| `source_line` | `INTEGER` | 否 | — | 关系发生处在 source 符号内的行号 |

**边类型语义：**

| `edge_type` | 含义 | 由谁产出 | 由谁消费 |
|---|---|---|---|
| `calls` | source 调用 target（`foo()`、`self.m()`、`alias.attr()`） | graph 阶段 | `find_references` |
| `imports` | source 模块 import target 模块 | graph 阶段 | `get_dependencies`、`get_dependents` |
| `inherits` | source 类继承 target 类 | graph 阶段 | （可用 SQL 查；暂无专用接口） |
| `references` | source 把 target 当值使用而非调用（`x = Cls`、注解、`isinstance`） | graph 阶段 | `find_references` |

---

## 5. 索引参考

在 `001_initial_schema.py` 中创建。

| 索引 | 表 | 定义 | 用途 |
|---|---|---|---|
| 主键（隐式） | 所有表 | `(id)` | 主键 |
| `ix_chunks_repo_file` | `chunks` | `(repo_id, file_path)` btree | 按仓库/文件扫描（文件大纲） |
| `ix_chunks_embedding_hnsw` | `chunks` | `hnsw (embedding vector_cosine_ops)` | 稠密（余弦）近邻检索 |
| `ix_chunks_tsv_gin` | `chunks` | `gin (tsv)` | 全文检索 —— **闲置**（`tsv` 未写入，见 §8） |
| `ix_symbols_repo_qname_unique` | `symbols` | `(repo_id, qualified_name)` **唯一** | 符号解析 + 唯一性 |
| `ix_edges_source` | `edges` | `(repo_id, source_id, edge_type)` | 正向遍历（依赖、调用出去） |
| `ix_edges_target` | `edges` | `(repo_id, target_id, edge_type)` | 反向遍历（引用、被依赖） |

---

## 6. 多租户与引用完整性

- **隔离**：每个子表行都带 `repo_id`；每条检索/图查询都 `WHERE repo_id = …`。
  不存在跨仓库查询路径。
- **级联**：删除 `repos` 行会删除其所有 `chunks`、`symbols`、`edges`
  （`ON DELETE CASCADE`）。删除 `chunks` 行会把引用它的 `symbols.chunk_id`
  置空（`ON DELETE SET NULL`），而非删除符号。
- **重新索引是按仓库全量替换**：worker 删除并重写全部 `chunks`，再删除并重写
  全部 `symbols`/`edges`，因此重索引同一仓库是幂等的（见 §11）。

---

## 7. 两个检索面速览

| | 语义面 | 结构面 |
|---|---|---|
| 表 | `chunks` | `symbols` + `edges` |
| 回答 | “关于 X 的代码”“`validate_token` 在哪” | “谁调用 X”“模块 M import 了啥”“文件 F 的大纲” |
| 机制 | 稠密向量（`embedding`）+ 稀疏关键词 | 按类型边遍历图 |
| 接口 | `/internal/search` | `find_definition` / `find_references` / `get_dependencies` / `get_dependents` / `get_file_outline` |

---

## 8. 语义面细节（`chunks.embedding`、`chunks.tsv`）

- **`embedding`** —— 稠密向量，经 HNSW 索引做余弦近邻。由 worker 的 embed 阶段
  写入。在 `EMBEDDING_MODEL=stub` 下向量全为零，且 API 查询侧编码器返回 `None`，
  因此**稠密检索失效、hybrid 退化为 sparse**（这就是已提交评测中 B2 = B3 = B4 的
  原因，见 `Final_Report_ch.md`）。真实向量需要 embedding sidecar（见
  [`Sidecar_Smoke_ch.md`](Sidecar_Smoke_ch.md)）。
- **`tsv`** —— 声明了 GIN 索引，但**从未写入**：embed 阶段不写 `tsv`，也没有触发器
  或生成列。API 的“sparse”检索也**不**用 `tsv` —— 它用
  `content/symbol_name/file_path ILIKE '%term%'` 加一个手写加权排序
  （`internal.py` 的 `_chunk_rank`）。全文基建目前处于休眠。
  （接真 BM25/`tsv` 已列入 backlog。）

### `/internal/search` 模式

| 模式 | 路径 |
|---|---|
| `sparse` | `ILIKE` 候选 → `_chunk_rank` 启发式 |
| `dense` | pgvector `cosine_distance`（stub 下为空 → 退回 sparse） |
| `hybrid` | sparse + dense → 加权 RRF（`dense:sparse = 2:1`，`k = 60`）→ reranker（stub 时为恒等） |

---

## 9. 结构面细节 + 接口→SQL 映射

每个内部图接口都是一条简单 SQL。符号解析先精确匹配 `qualified_name`，否则做后缀
`.<name>` 匹配。

| 接口 | 语义 | 底层查询（简化） |
|---|---|---|
| `find_definition?symbol=X` | X 定义在哪 | `SELECT * FROM symbols WHERE repo_id=? AND (qualified_name = X OR qualified_name LIKE '%.X')` |
| `find_references?symbol=X` | 谁调用/引用 X | 解析 X → `SELECT src FROM symbols src JOIN edges e ON e.source_id=src.id WHERE e.edge_type IN ('calls','references'[,'imports' 若为模块]) AND e.target_id IN (已解析)` |
| `get_dependencies?module=M` | M import 了谁 | 解析 M（kind=module）→ `edges` 中 `edge_type='imports' AND source_id IN (M)` → target 符号 |
| `get_dependents?module=M` | 谁 import 了 M | 解析 M（kind=module）→ `edges` 中 `edge_type='imports' AND target_id IN (M)` → source 符号 |
| `get_file_outline?path=P` | 文件 P 内的符号 | `SELECT * FROM symbols WHERE repo_id=? AND file_path=P ORDER BY line` |

对应的可复制 SQL 见 §15。

---

## 10. Redis 键空间

Redis 是缓存与实时状态存储，非持久真相。所有键由 `cache.py` 构建 —— 切勿内联拼键。

| 键模式 | 内容 | TTL |
|---|---|---|
| `embed:{model_id}:{sha256(text)}` | 某 chunk 内容的缓存向量 | 无（永久） |
| `tool:{tool_name}:{repo_id}:{sha256(args)[:16]}` | agent 工具结果缓存 | 24 小时（`tool_cache_ttl_seconds`） |
| `query:{repo_id}:{sha256(query)[:32]}` | 某查询的 SSE 字节流缓存（仅非错误） | 1 小时（`query_cache_ttl_seconds`） |
| `job:{repo_id}` | 实时 job 快照：`{status, progress, stages{}, error, warnings}` | 进行中无 TTL；完成后 7 天（`job_state_ttl_seconds`） |

状态接口（`GET /repos/{id}/status`）读 `job:{repo_id}` 获取实时分阶段进度与
warnings，缺失时回落到持久的 `repos` 行。

---

## 11. 写入路径（索引如何被填充）

worker 消费一个任务（`{repo_id, url}`）并运行单调状态机。每次转换都**双写**：
`repos` 行（Postgres）与 `job:{repo_id}` 快照（Redis）。

| 阶段（`repos.status`） | 运行器 | 写入的表 |
|---|---|---|
| `cloning` | `clone` | `repos`（`commit_sha`、status/progress） |
| `parsing` | `parse`、`chunk` | `repos`（status/progress）；在内存中构建 chunk 对象 |
| `embedding` | `embed` | **`chunks`**（全量替换：`DELETE WHERE repo_id` → 批量插入） |
| `graphing` | `graph` | **`symbols`** 再 **`edges`**（全量替换：删边 → 删符号 → 插符号 → flush → 插边） |
| `ready` | — | `repos`（status=ready，progress=100） |

关键性质：

- **顺序有讲究**：embed 在 graph 之前提交 `chunks`，这样 graph 阶段才能把
  `symbols.chunk_id` 链接到刚写入的 chunk。
- **全量替换 = 幂等**：重索引仓库会干净地覆盖其行。worker 崩溃 → RabbitMQ 重投
  未 ack 的任务 → 干净重跑。
- **失败**：任一阶段出错会把 `repos.status='failed'` 并写 `error` 和失败阶段的
  `in_progress` 进度百分比。中途被删的仓库会被丢弃而不使消息失败
  （`handle_job` 恒不抛）。
- **提交频率**：一次成功任务约 9 次 `repos` 提交（每阶段 2 次 + 最终 1 次）。

---

## 12. 读取路径（谁读什么）

- **API `/internal/*`**（被 agent 与评测 harness 读取）：读 `chunks`（检索）、
  `symbols` + `edges`（图谱）、`repos`（存在性检查）。
- **Agent groundedness 校验**：agent 唯一直接碰 DB 的地方 —— 把每条引用对照
  `chunks`（`[start_line, end_line]` 包含被引行的 chunk）与 `symbols`
  （精确 `qualified_name`）核实。
- **状态接口**：读 `repos` + Redis `job:` 快照。

---

## 13. 迁移与 schema 管理

- schema 由 **Alembic 迁移 `001_initial_schema`** 创建（`infra/migrations/`）。
  `infra/postgres/init.sql` 仅在容器首次启动时执行
  `CREATE EXTENSION IF NOT EXISTS vector`。
- 应用迁移：

  ```bash
  make migrate           # docker compose exec api uv run alembic ... upgrade head
  # 或直接：
  uv run alembic -c infra/migrations/alembic.ini upgrade head
  ```

- **`EMBEDDING_DIM` 在迁移时被固化进 `chunks.embedding` 列**
  （`Vector(shared_settings.embedding_dim)`）。默认是 `1024`（stub）；Jina v2 真实
  向量是 `768`。首次迁移后更改维度需要重建卷：

  ```bash
  docker compose down -v && make migrate    # 会销毁本地数据
  ```

---

## 14. 用 `psql` 连接与查看

```bash
# 只启动 Postgres（复用 postgres_data 卷）
docker compose up -d --wait postgres

# 交互式 shell（默认用户/库均为 'dcode'，来自 .env）
docker compose exec postgres psql -U dcode -d dcode

# 一次性查询，非交互
docker compose exec -T postgres psql -U dcode -d dcode -c "SELECT count(*) FROM chunks;"
```

常用 `psql` 元命令：`\dt`（列出表）、`\d chunks`（查看某表结构与索引）、
`\x`（宽行竖排输出）、`\q`（退出）。

**注意事项：**

- **切勿对 `chunks` 用 `SELECT *`** —— `embedding`（数百个浮点）与 `tsv` 会刷屏。
  始终显式列出列。
- 本地 dev 卷可能存有**同一仓库的多份副本**（每次提交是一个不同的 `repos.id`）。
  查询时 scope 到一个仓库，例如
  `WHERE repo_id = (SELECT id FROM repos ORDER BY created_at LIMIT 1)`。

---

## 15. SQL 手册

这些直接对应 app 自身的操作。

```sql
-- 登记表概况 + 行数
SELECT id, url, status, progress FROM repos;
SELECT 'chunks' t, count(*) FROM chunks
UNION ALL SELECT 'symbols', count(*) FROM symbols
UNION ALL SELECT 'edges',   count(*) FROM edges;

-- （= get_file_outline）某文件内定义的符号
SELECT qualified_name, kind, line
FROM symbols
WHERE file_path = 'src/requests/auth.py'
ORDER BY line;

-- （= find_definition）某符号定义在哪
SELECT qualified_name, kind, file_path, line
FROM symbols
WHERE qualified_name LIKE '%.HTTPBasicAuth';

-- （= find_references）谁调用了某函数
SELECT s.qualified_name AS caller, t.qualified_name AS callee, e.source_line
FROM edges e
JOIN symbols s ON s.id = e.source_id
JOIN symbols t ON t.id = e.target_id
WHERE e.edge_type = 'calls'
  AND t.qualified_name LIKE '%.send';

-- （= get_dependencies）某模块 import 了谁
SELECT s.qualified_name AS importer, t.qualified_name AS imported
FROM edges e
JOIN symbols s ON s.id = e.source_id
JOIN symbols t ON t.id = e.target_id
WHERE e.edge_type = 'imports'
  AND s.file_path = 'src/requests/sessions.py';

-- 查看某个 chunk 的原始源码（content 就是原代码）
SELECT file_path, symbol_name, content
FROM chunks
WHERE symbol_name = 'HTTPBasicAuth';

-- （= sparse 检索，近似）关键词扫描代码
SELECT file_path, symbol_name, start_line, end_line
FROM chunks
WHERE content ILIKE '%Authorization%'
LIMIT 20;

-- 分布统计
SELECT chunk_type, count(*) FROM chunks GROUP BY chunk_type ORDER BY 2 DESC;
SELECT edge_type,  count(*) FROM edges  GROUP BY edge_type;
SELECT file_path, count(*) AS symbols FROM symbols GROUP BY file_path ORDER BY 2 DESC LIMIT 10;
```

---

## 16. 向量相似度查询（pgvector）

`embedding` 列只有通过向量距离算子才有意义，纯文本看没用。pgvector 提供：

| 算子 | 距离 | 匹配 HNSW 索引？ |
|---|---|---|
| `<=>` | 余弦距离 | **是**（`vector_cosine_ops`） |
| `<->` | L2（欧氏） | 否 |
| `<#>` | 负内积 | 否 |

要按语义相似度排序 chunk，需要一个**查询向量**（用同一模型编码问题）。示例
（`$1` = 一个 768 维浮点字面量 `'[0.01, -0.02, …]'::vector`）：

```sql
SELECT file_path, symbol_name, 1 - (embedding <=> $1) AS cosine_similarity
FROM chunks
WHERE repo_id = :repo_id
ORDER BY embedding <=> $1     -- 距离升序 = 最相似在前
LIMIT 10;
```

这与 `internal.py` 的 `_search_dense_candidates` 一致。stub 向量下没有查询向量
（全零），此路返回不了有用结果 —— 请先启用真实 sidecar。

---

## 17. 运维坑点

1. **维度陷阱。** `chunks.embedding` 固定为迁移时的 `EMBEDDING_DIM`。以 768 迁移的卷
   会拒绝 1024 维插入（反之亦然）。让 `EMBEDDING_DIM` 与卷一致，或 `down -v` + 重迁移。
2. **stub vs 真实。** stub 向量是 1024 维全零，重读时被当作缓存未命中（所以 stub
   模式没有有效缓存，每次都重写零向量）。真实 Jina v2 向量是 768 维非零浮点 —— 一条
   `SELECT vector_dims(embedding), left(embedding::text, 20) FROM chunks LIMIT 1;`
   即可判断你拿到的是哪种。
3. **`tsv` / GIN 闲置。** 全文列及其索引存在但未被使用（§8）。别以为关键词检索走了
   GIN 索引 —— 它走 `ILIKE`。
4. **图谱 v1 覆盖度。** 仅基于名称的静态分析：无类型推断、继承来的 `self.method()`
   无 MRO 解析、无嵌套函数/类符号、装饰器不计入 chunk/符号行范围。把图谱当作
   尽力而为的静态证据。
5. **进行中 job 状态无 TTL。** 崩溃的任务会留下一个无 TTL 的 `job:{repo_id}` 键，
   直到一次重跑将其完成。
6. **部分失败窗口。** `chunks`（embed）与 `symbols`/`edges`（graph）在不同事务中提交；
   两者之间失败会让仓库处于 `failed`，且有新 chunk 但图谱行陈旧/缺失，直到成功重索引。

---

## 18. 当前 dev 卷快照

在本地 `dcode_postgres_data` 卷上查得（仅供参考；你的卷可能不同）：

| 项 | 值 |
|---|---|
| `repos` | 2 行，均为 `https://github.com/psf/requests.git`，均 `ready`，commit `f361ead047` |
| `chunks` | 1452（每仓库 726） |
| `symbols` | 1448 |
| `edges` | 736 —— `calls` 606、`imports` 130 |
| `embedding` 维度 | **768**（真实 Jina v2 代码向量，非 stub） |
| 索引时间 | 2026-07-12 与 2026-07-13 |
| `chunk_type` 分布（单仓库） | `method` 489、`function` 146、`class` 72、`module_doc` 19 |

注意：这批数据**早于 `inherits`/`references` 边的实现**，故 `edges` 只含
`calls` + `imports`。用当前 worker 重索引会补上这两类较新的边。

---

## 关联文档

- [`Technical_Design_ch.md`](Technical_Design_ch.md) —— 架构、API 契约、NFR
- [`Sidecar_Smoke_ch.md`](Sidecar_Smoke_ch.md) —— 真实 embedding/reranker 路径 + DB 维度重建
- [`Final_Report_ch.md`](../../ch/Final_Report_ch.md) —— 评测快照与 H1 结论
- [`Outstanding_Work_ch.md`](Outstanding_Work_ch.md) —— 遗留工作（含 `tsv`/BM25、更丰富的图边）
