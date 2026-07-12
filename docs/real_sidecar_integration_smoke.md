# 真实模型 Sidecar 集成 Smoke 复现指南

## 目的

本文档记录真实 embedding 与 reranker 模式下的本地集成 smoke 流程，供后续检索评测、H1 复测和 Compare 页刷新前复用。

本文档覆盖集成验证。完整指标刷新仍以 eval suite 为准。验证重点如下：

- worker 通过 Jina v2 embedding sidecar 写入 768 维向量；
- API 使用查询侧 embedding 和 BGE reranker 返回真实 `dense` 与 `rerank` 分数；
- worker graph 阶段写入真实调用边；
- agent 通过既有内部 API 契约调用 `/internal/search` 和 `/internal/find_references`；
- `/api/v1/query` 返回带已验证引用的 SSE 结果。

完成该流程后，eval owner 可在此基础上运行 `results/eval-suite/` 的正式评测。

## 适用范围

适用于本地开发环境，尤其是 MacBook 上将 embedding 与 reranker 模型运行在 host 侧，并让 Docker Compose 服务通过 `host.docker.internal` 访问模型 sidecar 的场景。

当前推荐模型配置：

| 项 | 值 |
|---|---|
| Embedding model | `jinaai/jina-embeddings-v2-base-code` |
| Embedding dimension | `768` |
| Embedding endpoint | `http://host.docker.internal:8002` |
| Reranker model | `BAAI/bge-reranker-v2-m3` |
| Reranker endpoint | `http://host.docker.internal:8003` |
| Target repo | `https://github.com/psf/requests.git` |

## 前置条件

- Docker Desktop 已启动；
- 本地 Python 和 `uv` 环境可用；
- 已在仓库根目录；
- `.env` 存在并包含本地开发所需的数据库、Redis、RabbitMQ、internal API key 配置；
- 首次运行模型会从 Hugging Face 下载权重，需要网络和足够磁盘空间；
- 建议本机至少 16 GB RAM。

先确认本地代码和基础测试状态：

```bash
git status --short --branch
git pull --ff-only
make check
```

## 1. 配置真实 Sidecar 环境变量

编辑 `.env`，把 embedding 与 reranker 配置为真实模型：

```dotenv
EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
EMBEDDING_DIM=768
EMBEDDING_ENDPOINT=http://host.docker.internal:8002

RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_ENDPOINT=http://host.docker.internal:8003
```

注意：`.env` 是本地文件，请不要提交。

## 2. 重建数据库 volume

`chunks.embedding` 的 pgvector 维度在 migration 时固定。如果旧数据库曾用默认 `EMBEDDING_DIM=1024` 初始化，直接切到 Jina v2 的 768 维会导致索引写入失败。

检查当前列维度：

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select atttypmod from pg_attribute where attrelid='chunks'::regclass and attname='embedding';"
```

如果返回 `1024`，需要重建本地 volume：

```bash
docker compose down -v
docker compose up -d postgres redis rabbitmq
docker compose up -d api worker agent frontend
make migrate
```

再次确认维度应为 `768`：

```bash
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select atttypmod from pg_attribute where attrelid='chunks'::regclass and attname='embedding';"
```

说明：`docker compose down -v` 会删除本地数据库和 worker volume。该操作只适合可丢弃的本地 smoke 环境；需要保留数据时请先备份或使用新的 volume。

## 3. 启动模型 Sidecar

在两个独立终端启动 host 侧模型服务：

```bash
make embedding-host
```

等待日志出现：

```text
Embedding model ready. max_seq_length=1024
```

另一个终端启动 reranker：

```bash
make reranker-host
```

等待日志出现：

```text
Reranker model ready
```

健康检查：

```bash
curl -fsS http://localhost:8002/healthz
curl -fsS http://localhost:8003/healthz
```

期望返回类似：

```json
{"status":"ok","model":"jinaai/jina-embeddings-v2-base-code"}
{"status":"ok","model":"BAAI/bge-reranker-v2-m3"}
```

## 4. 重建并启动主服务

```bash
docker compose build api worker agent
docker compose up -d api worker agent frontend postgres redis rabbitmq
make migrate
make smoke
```

`make smoke` 应返回：

```text
API:
{"status":"ok"}
Agent:
{"status":"ok"}
Frontend:
OK
```

确认 API 容器读到真实模型配置：

```bash
docker compose exec -T api env | rg '^(EMBEDDING_MODEL|EMBEDDING_DIM|EMBEDDING_ENDPOINT|RERANKER_MODEL|RERANKER_ENDPOINT)='
```

应看到：

```text
EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
EMBEDDING_DIM=768
EMBEDDING_ENDPOINT=http://host.docker.internal:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_ENDPOINT=http://host.docker.internal:8003
```

## 5. 重新索引 `psf/requests`

提交索引任务：

```bash
curl -fsS -X POST http://localhost:8000/api/v1/repos \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://github.com/psf/requests.git"}'
```

记录返回的 `repo_id`。后续命令用 `<repo_id>` 代替。

轮询状态：

```bash
curl -fsS "http://localhost:8000/api/v1/repos/<repo_id>/status" | python3 -m json.tool
```

完成状态应为：

```json
{
  "status": "ready",
  "progress": 100,
  "stages": {
    "cloning": "done",
    "parsing": "done",
    "embedding": "done",
    "graphing": "done"
  }
}
```

真实 embedding 阶段通常比 stub 模式慢。可用 worker 日志确认进度：

```bash
docker compose logs --tail=120 worker
```

应能看到 worker 调用 embedding sidecar：

```text
using HTTP embedding client model=jinaai/jina-embeddings-v2-base-code endpoint=http://host.docker.internal:8002
HTTP Request: POST http://host.docker.internal:8002/embed "HTTP/1.1 200 OK"
```

## 6. 数据库验证

确认 repo ready，以及 chunk 和 symbol 数量：

```bash
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select r.id, r.status, r.progress, count(distinct c.id) as chunks, count(distinct s.id) as symbols from repos r left join chunks c on c.repo_id=r.id left join symbols s on s.repo_id=r.id where r.id='<repo_id>' group by r.id;"
```

确认 embedding 维度：

```bash
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select vector_dims(embedding) as dims, count(*) from chunks where repo_id='<repo_id>' group by dims;"
```

确认 graph edge 计数：

```bash
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select edge_type, count(*) from edges where repo_id='<repo_id>' group by edge_type order by edge_type;"
```

最近一次本地 smoke 的参考结果：

| 项 | 值 |
|---|---:|
| chunks | 726 |
| symbols | 724 |
| embedding dims | 768 |
| calls | 303 |
| imports | 65 |

这些数值仅用于 smoke 对照，正式评测以 eval suite 输出为准。

## 7. 内部 API 验证

设置变量，便于复用命令：

```bash
export REPO_ID=<repo_id>
export INTERNAL_API_KEY=dev-internal-key-change-me
```

确认 `/internal/search` 返回真实 dense 与 rerank 分数：

```bash
curl -fsS "http://localhost:8000/internal/search?repo_id=${REPO_ID}&query=HTTPBasicAuth%20Authorization%20header&k=5" \
  -H "X-Dcode-Internal-Key: ${INTERNAL_API_KEY}" \
  | python3 -m json.tool
```

检查点：

- 第一批结果应包含 `src/requests/auth.py`；
- `score_components.dense` 应为非零真实分数；
- `score_components.rerank` 应为 BGE reranker 返回的真实分数；
- reranker sidecar 日志应出现 `POST /rerank`。

确认 `find_references(symbol=send)` 返回真实调用方：

```bash
curl -fsS "http://localhost:8000/internal/find_references?repo_id=${REPO_ID}&symbol=send" \
  -H "X-Dcode-Internal-Key: ${INTERNAL_API_KEY}" \
  | python3 -m json.tool
```

参考返回应包含：

- `src.requests.sessions.SessionRedirectMixin.resolve_redirects`
- `src.requests.sessions.Session.request`

## 8. Agent SSE 验证

清理本地 Redis query cache，避免命中旧查询结果：

```bash
docker compose exec -T redis redis-cli FLUSHDB
```

通过 public API gateway 运行 agent query：

```bash
curl -fsS -N -X POST http://localhost:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d "{\"repo_id\":\"${REPO_ID}\",\"query\":\"Who calls send in requests?\"}"
```

检查点：

- `thought` 应显示路由到 `find_references`；
- `tool_call.args.symbol` 应为 `send`；
- `tool_result` 应显示至少 2 个 locations；
- `citation` 事件应包含已验证引用；
- `final_answer.groundedness` 应为 `1.0`。

该验证用于确认 agent 能够消费 Yuxin(Lacey)Liang 的 retrieval 和 graph stack，并且内部 API 契约保持兼容。

## 9. 测试命令

完成集成 smoke 之后建议至少运行：

```bash
make check
make smoke
```

如果需要验证 live internal fixture：

```bash
DCODE_LIVE_REPO_ID=${REPO_ID} \
INTERNAL_API_KEY=${INTERNAL_API_KEY} \
PYTHONPATH=packages/shared/src:apps/api/src \
uv run pytest apps/api/tests/test_internal_validation.py -q
```

## 10. 交接给后续评测

完成本文档中的 smoke 后，可以交给 eval 和 frontend owner 执行后续工作：

1. 使用同一套真实 sidecar 配置重新跑 B1/B2/B3/B4；
2. 重新生成 `results/eval-suite/`；
3. 检查 B1/B2/B3/B4 是否仍复用同一 `/internal/search` 路径，必要时拆分 baseline retrieval path；
4. 用新结果更新 frontend `evalSnapshot.ts`；
5. 基于新结果重新判断 H1。

重要边界：

- 本文档覆盖集成 smoke；H1 结论以完整 eval suite 为准；
- 本文档中的 repo_id 是本地数据库产物，换环境后会变化；
- 真实评测必须记录模型配置、数据库维度、repo commit、问题集版本和输出目录；
- 更新 H1 前必须重新生成并审查完整 eval suite。
