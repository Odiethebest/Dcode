# Dcode Operations

Running the stack, reproducing the real-model path, running the evaluation
harness, and the failure modes worth recognising before you hit them.

## Bringing the stack up

A fresh `cp .env.example .env` uses stub embedding and identity reranking, so
`make up` is sufficient for lightweight development. For the real-model path,
set `EMBEDDING_ENDPOINT` / `RERANKER_ENDPOINT` to
`host.docker.internal:8002`/`8003` and select the Jina/BGE model names described
below. The models then run as **host** sidecars, which means three processes, not
one:

```bash
make embedding-host   # :8002 — wait for "Embedding model ready"
make reranker-host    # :8003 — wait for "Reranker model ready"
make up               # core stack: postgres, redis, rabbitmq, api, agent, worker
```

The Docker `embedding` / `reranker` Compose profiles are the alternative and need
roughly 6 GB of Docker RAM.

```bash
make ps / make logs / make smoke / make down / make down-all
make migrate                            # Alembic upgrade head inside the api container
make check                              # lint + typecheck + tests + eval-artifact drift check
make frontend-build
npm --prefix apps/frontend run dev      # → http://localhost:5173/
python3 scripts/sync_eval_artifacts.py [--check] [results/eval-h1-repeat3-2026-07-31]
make eval-smoke                         # single-baseline harness smoke
```

Then in the workbench: index a repository via the switcher, watch
`queued → … → ready`, select it, and ask. A first real index runs Jina embeddings
on CPU, so a real repository takes several minutes and **plateaus visibly at the
embedding stage — that is real work, not a hang.**

### Two startup failure modes

- **With real-model endpoint values configured, `make up` alone** gives a stack
  whose API reports healthy while every query dies at the embedding step. The
  sidecars are not optional in that configuration. Stub mode does not need them.
- **A wall of Vite `ECONNREFUSED` on `/api/v1/*`** in the dev-server log means the
  backend is down, not that the frontend broke.

## Operational gotchas

These have each cost someone real time.

1. **The embedding-dimension trap.** `chunks.embedding` is fixed to whatever
   `EMBEDDING_DIM` was at migration time. A volume migrated at 768 will reject
   1024-dim inserts and vice-versa. Match `EMBEDDING_DIM` to the volume, or
   `make down-all` and re-migrate. This is the single most common way to lose an
   afternoon here.
2. **Telling stub vectors from real ones.** Stub embeddings are 1024-dim
   all-zeros, and they are treated as a cache miss on re-read — so stub mode does
   no effective caching and rewrites zeros every run. Real Jina v2 vectors are
   768-dim non-zero floats. One query settles which you have:

   ```sql
   SELECT vector_dims(embedding), left(embedding::text, 20) FROM chunks LIMIT 1;
   ```

3. **`tsv` and its GIN index are idle.** The retained full-text column is not the
   sparse path. Sparse search builds a code-tokenized Okapi BM25 corpus in the
   API and caches it by `repo_id + index_revision`; the worker increments that
   revision whenever it atomically replaces the chunks.
4. **Graph coverage is name-based static analysis only.** No type inference, no
   MRO resolution for inherited `self.method()` calls, no nested-function or
   nested-class symbols, and decorators are excluded from chunk and symbol line
   ranges. Treat the graph as best-effort static evidence.
5. **In-progress job state has no TTL.** A crashed indexing job leaves a
   TTL-less `job:{repo_id}` key in Redis until a re-run completes it.
6. **There is a partial-failure window.** `chunks` (embed stage) and
   `symbols`/`edges` (graph stage) commit in separate transactions. A failure
   between them leaves the repo `failed` with new chunks but stale or missing
   graph rows, until a successful re-index.
7. **Skipped-file warnings are ephemeral.** They live only in the Redis job state
   on a 7-day TTL, so an older index honestly reports none rather than a stale
   count. The UI surfaces them while they exist.

## Real-model smoke

The reproducible local flow for running Dcode with real embedding and reranker
sidecars — for evaluation refreshes and H1 re-runs.

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

Directed call lookup keeps incoming and outgoing `calls` edges separate:

```bash
curl -fsS "http://localhost:8000/internal/get_call_neighbors?repo_id=${REPO_ID}&symbol=send&direction=both" \
  -H "X-Dcode-Internal-Key: ${INTERNAL_API_KEY}" \
  | python3 -m json.tool
```

The response includes `matches`, `callers`, `callees`, and `source_calls`.
Each source call has a `resolved_target` or an explicit `null`; an empty graph
group therefore does not conceal dynamic/instance calls present in source.

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

- `thought` routes to `get_call_neighbors`;
- `tool_call.args` includes `symbol=send` and `direction=callers`;
- `tool_result` reports matched symbols and caller/callee counts;
- a follow-up `read_file` captures source-level calls that the static graph may not resolve;
- `citation` events include verified references;
- `final_answer.groundedness` is `1.0`.

## Running the evaluation harness

Once the smoke passes:

0. **Flush Redis first** (`docker exec dcode-redis-1 redis-cli FLUSHALL`) and
   record that you did. The agent caches tool results for 24h under
   `tool:<name>:<repo_id>:<hash>`, so a run started against a warm cache can be
   served graph results produced by *older agent code* whose shape the current
   scoring protocol does not fully read. This is not hypothetical: the 2026-07-31
   run was aborted mid-B3 and restarted for exactly this reason.
1. Run B1–B4 under the same real sidecar configuration, writing to a **new**
   results directory. Do not overwrite any committed snapshot, including
   `results/eval-h1-repeat3-2026-07-31/`, `results/eval-h1-bm25-2026-07-30/` and
   `results/eval-real/` — see [`results/README.md`](../../results/README.md).
   Pass `--repo-id`; the harness then records the database's exact
   `corpus_revision` together with the BM25 formula, tokenizer, document fields,
   `k1`, and `b` in both suite and per-baseline `run_config.json` files. It reads
   the revision again after the run and rejects the result if the repository was
   re-indexed in between.
2. Regenerate every artifact that displays the numbers, then verify:

   ```bash
   python3 scripts/sync_eval_artifacts.py results/<new-run>
   python3 scripts/sync_eval_artifacts.py --check
   ```

   The generator formats the TypeScript snapshot through the frontend's locked
   Prettier binary before comparing or writing it.

3. **Re-read the prose.** Tests and the drift check follow the data; the narrative
   copy in the README, [`Final_Report.md`](Final_Report.md), and the
   `/methodology` page does not. Correct any claim the new numbers no longer
   support.
4. Reassess H1 against the criteria in [`Final_Report.md`](Final_Report.md), and
   report whichever way it lands.

Criteria set 3 items 1–3 are done and were run: one scoring rule for every agent
arm, a `dense_only` B2, and the `B3.5` no-graph ablation. The composite also
dropped groundedness, and the suite is now averaged over three repeats. The
current verdict is `results/eval-h1-repeat3-2026-07-31/`.

**Before the next H1 run, read this.** The L2 shortfall is 0.006 against a
between-repeat standard deviation of 0.034. Four single runs before the repeated
one each "just missed", on alternating levels, and repeat 3 of the current run
cleared everything on its own. **Another round of system tuning cannot be
attributed to the tuning at this effect size.** What is left is more L2 questions
or a second corpus — criteria set 3 item 5.

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

Historical caveat: at the time of this run, planner and synthesis were
rule-based, so the final answer was a grounded, citation-backed trace rather
than LLM prose. The planner remains rule-based, but current deployments may set
`SYNTHESIS_MODEL` to an LLM; do not treat this 2026-07-27 smoke as validation of
the later citation-ID, language, math, or multi-turn contracts.

## Verified Current Path — 2026-07-30

The current local integration configuration used Jina 768-dimensional
embeddings, the BGE reranker, and `gpt-4o-mini` synthesis. All seven core Docker
services and both host model sidecars were healthy. A live
`POST /api/v1/query` for *"Who calls send?"* exercised the explicit caller route
and server-owned evidence-ID path, returning:

- `src/requests/sessions.py:186`;
- `src/requests/sessions.py:557`;
- both citations with `verified=true`;
- final groundedness `1.0`.

This is a one-question integration smoke. It proves the current service path
works end to end; by itself it does not establish suite-level behavior.

## Complete BM25 H1 Re-run — 2026-07-30

The complete B1–B4 harness subsequently ran against repo
`2543893e-0965-4be7-ac45-5a8e38600bc0`, commit
`414f0513c33883adf6f2b46901d4f0b38a455851`, with all 726 chunks embedded at
768 dimensions. Redis was flushed before the run; Jina v2-base-code, BGE
reranker v2-m3, and `gpt-4o-mini` were healthy and active. The runner completed
all 16 questions for each baseline, observed the same corpus revision before
and after, and exited successfully.

The recorded output is `results/eval-h1-bm25-2026-07-30/`, now **superseded**. It
validated the corrected Okapi BM25 path and the evidence-ID groundedness path.
H1 was `unsupported`: B4 beat B2 on L2, lost slightly on L3, and tied B3 on both
levels because that harness gave B3 and B4 the same scored retrieval list.

## L3-expanded single runs — 2026-07-31

Four single runs, all superseded by the repeated run below and all retained:
`eval-h1-l3x12` (33-question suite, mixed scoring), `eval-h1-uniform-v2` (one
scoring rule for every arm, `B3.5` added), `eval-h1-ranked-evidence` (graph
evidence hydrated and reranked), `eval-h1-no-test-evidence` (test code excluded
from retrieval). Each "just missed" on one level, and which level alternated.
That pattern is what motivated repeating the suite.

## Repeated H1 Run — 2026-07-31 (current)

Same repo `2543893e-0965-4be7-ac45-5a8e38600bc0`, same commit
`414f0513c33883adf6f2b46901d4f0b38a455851`, same 726 chunks at 768 dimensions and
the same `index_revision` as every run above, so differences between them are
protocol and agent, never corpus.

Five arms including the `B3.5` ablation, the frozen 33-question suite, **three
repeats averaged**, under `uniform_final_verified_evidence_v2` and the three-term
composite — both declared and committed before this run existed. Redis was
flushed once before repeat 1 and deliberately not between repeats: tool results
are deterministic for a fixed index, and the stochastic stage is synthesis, which
is never cached. Zero API or agent errors; same corpus revision before and after.

Output: `results/eval-h1-repeat3-2026-07-31/`. H1 is `unsupported` — three of the
four required comparisons clear, and `B4 vs B3` on L2 falls 0.006 short.

**The number to take from this run is the spread, not the margin.** Across the
three repeats the L2 margin was +0.038, +0.006 and +0.088 — a range of 0.083,
wider than the 0.050 bar — and **repeat 3 returned `supported` on its own**. Each
repeat keeps its complete independent output under `repeat-N/` with its own
`h1_report.json`, so that is checkable rather than asserted. Read
`provenance.json` and the *Reading the result honestly* section of
[`Final_Report.md`](Final_Report.md) before quoting any figure from here.
