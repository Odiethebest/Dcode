# Real Sidecar Smoke Guide

## Purpose

This guide documents the reproducible local smoke flow for running Dcode with real embedding and reranker sidecars. It is intended for later evaluation refreshes, H1 reruns, and Compare page updates.

The smoke validates that:

- the worker writes 768-dimensional Jina v2 embeddings;
- the API returns real dense and rerank score components;
- the worker graph stage writes real call edges;
- the agent consumes the unchanged internal API contract;
- `/api/v1/query` returns SSE answers with verified citations.

This guide covers integration smoke. Full metrics should still come from the evaluation suite.

## Recommended Configuration

| Item | Value |
|---|---|
| Embedding model | `jinaai/jina-embeddings-v2-base-code` |
| Embedding dimension | `768` |
| Embedding endpoint | `http://host.docker.internal:8002` |
| Reranker model | `BAAI/bge-reranker-v2-m3` |
| Reranker endpoint | `http://host.docker.internal:8003` |
| Target repository | `https://github.com/psf/requests.git` |

## Prerequisites

- Docker Desktop is running.
- Python and `uv` are available.
- Commands are run from the repository root.
- `.env` contains local database, Redis, RabbitMQ, and internal API key settings.
- The first model run can download weights from Hugging Face.
- A machine with at least 16 GB RAM is recommended.

Run the baseline checks first:

```bash
git status --short --branch
git pull --ff-only
make check
```

## Configure Environment

Set the real sidecar values in `.env`:

```dotenv
EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
EMBEDDING_DIM=768
EMBEDDING_ENDPOINT=http://host.docker.internal:8002

RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_ENDPOINT=http://host.docker.internal:8003
```

Do not commit `.env`.

## Rebuild the Database Volume

`chunks.embedding` has a fixed pgvector dimension after migration. If the database was initialized with `EMBEDDING_DIM=1024`, switching directly to Jina v2 768-dimensional vectors will fail.

Check the current dimension:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select atttypmod from pg_attribute where attrelid='chunks'::regclass and attname='embedding';"
```

If the result is `1024`, rebuild the local volume:

```bash
docker compose down -v
docker compose up -d postgres redis rabbitmq
docker compose up -d api worker agent frontend
make migrate
```

Confirm the dimension is now `768`:

```bash
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select atttypmod from pg_attribute where attrelid='chunks'::regclass and attname='embedding';"
```

This deletes local database and worker volumes. Use it only for disposable local smoke environments.

## Start Sidecars

Start the embedding host in one terminal:

```bash
make embedding-host
```

Wait for:

```text
Embedding model ready. max_seq_length=1024
```

Start the reranker host in another terminal:

```bash
make reranker-host
```

Wait for:

```text
Reranker model ready
```

Health checks:

```bash
curl -fsS http://localhost:8002/healthz
curl -fsS http://localhost:8003/healthz
```

## Rebuild Services

```bash
docker compose build api worker agent
docker compose up -d api worker agent frontend postgres redis rabbitmq
make migrate
make smoke
```

Confirm the API container sees the real configuration:

```bash
docker compose exec -T api env | rg '^(EMBEDDING_MODEL|EMBEDDING_DIM|EMBEDDING_ENDPOINT|RERANKER_MODEL|RERANKER_ENDPOINT)='
```

## Re-Index `psf/requests`

Submit the repository:

```bash
curl -fsS -X POST http://localhost:8000/api/v1/repos \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://github.com/psf/requests.git"}'
```

Record the returned `repo_id`, then poll:

```bash
curl -fsS "http://localhost:8000/api/v1/repos/<repo_id>/status" | python3 -m json.tool
```

The final status should be `ready` with all stages marked `done`.

## Validate Database State

Check chunks, symbols, and graph edges:

```bash
docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select r.id, r.status, r.progress, count(distinct c.id) as chunks, count(distinct s.id) as symbols from repos r left join chunks c on c.repo_id=r.id left join symbols s on s.repo_id=r.id where r.id='<repo_id>' group by r.id;"

docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select vector_dims(embedding) as dims, count(*) from chunks where repo_id='<repo_id>' group by dims;"

docker compose exec -T postgres psql -U dcode -d dcode \
  -c "select edge_type, count(*) from edges where repo_id='<repo_id>' group by edge_type order by edge_type;"
```

Recent local smoke reference values:

| Item | Value |
|---|---:|
| chunks | 726 |
| symbols | 724 |
| embedding dims | 768 |
| calls | 303 |
| imports | 65 |

## Validate Internal API

```bash
export REPO_ID=<repo_id>
export INTERNAL_API_KEY=dev-internal-key-change-me
```

Search should return real dense and rerank score components:

```bash
curl -fsS "http://localhost:8000/internal/search?repo_id=${REPO_ID}&query=HTTPBasicAuth%20Authorization%20header&k=5" \
  -H "X-Dcode-Internal-Key: ${INTERNAL_API_KEY}" \
  | python3 -m json.tool
```

Reference lookup should return real callers for `send`:

```bash
curl -fsS "http://localhost:8000/internal/find_references?repo_id=${REPO_ID}&symbol=send" \
  -H "X-Dcode-Internal-Key: ${INTERNAL_API_KEY}" \
  | python3 -m json.tool
```

Expected references include:

- `src.requests.sessions.SessionRedirectMixin.resolve_redirects`
- `src.requests.sessions.Session.request`

## Validate Agent SSE

Clear local Redis query cache:

```bash
docker compose exec -T redis redis-cli FLUSHDB
```

Run the public query flow:

```bash
curl -fsS -N -X POST http://localhost:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d "{\"repo_id\":\"${REPO_ID}\",\"query\":\"Who calls send in requests?\"}"
```

Expected checkpoints:

- `thought` routes to `find_references`;
- `tool_call.args.symbol` is `send`;
- `tool_result` includes at least two locations;
- `citation` events include verified references;
- `final_answer.groundedness` is `1.0`.

## Follow-Up Evaluation

After the smoke passes, evaluation and frontend owners can:

1. rerun B1/B2/B3/B4 with the same real sidecar configuration;
2. regenerate `results/eval-suite/`;
3. verify baseline retrieval paths are independent;
4. update frontend `evalSnapshot.ts`;
5. reassess H1 from the refreshed results.

## Verified Run — 2026-07-27

A local real-model run against the committed `psf/requests` index (768-dim
Jina, `repo_id` `bfe447be…`) confirmed the full path end-to-end. Sidecars were
launched on the host via `make embedding-host` / `make reranker-host` (both host
scripts export `PYTHONPATH` so the workspace app is importable); the API ran in
Docker with `EMBEDDING_MODEL` / `RERANKER_MODEL` pointed at the host sidecars.

- **Semantic retrieval works with zero keyword overlap.** For the query
  *"how does it attach the user credentials to prove identity to the server"*
  (no `auth` / `Authorization` / `HTTPBasicAuth` tokens): `mode=sparse` returned
  only unrelated `tests/` files, while `mode=dense` returned
  `src/requests/auth.py` (the `HTTP*Auth` constructors, cosine ≈ 0.52) as the top
  hits.
- **The reranker improves precision.** For *"store and reuse cookies across
  multiple requests"*, `mode=dense` returned five `tests/test_requests.py` hits;
  the full `mode=hybrid` (BGE reranker) flipped all five to
  `src/requests/{sessions,cookies}.py`.
- **Agent SSE end-to-end.** `POST /api/v1/query` ran `plan → search_code`
  (top hit `src/requests/auth.py`) `→ read_file → find_references →
  get_file_outline → synthesize`, emitting 14 citations all `verified=True` with
  `groundedness=1.0`.

Caveat unchanged: the agent planner/synthesis are rule-based, so the final
answer is a grounded, citation-backed trace rather than LLM prose.
