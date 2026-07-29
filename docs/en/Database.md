# Dcode Database Reference

This document is the authoritative reference for Dcode's persistence layer: the
PostgreSQL schema (tables, columns, enums, indexes, constraints), the Redis
keyspace, how data is written and read, and how to inspect it with SQL. It
expands [`Technical_Design.md` §3 (Data Model)](Technical_Design.md) with
column-level detail and an operational SQL cookbook.

**Source of truth in code:**

| Concern | File |
|---|---|
| ORM models (tables, columns, relationships) | `packages/shared/src/dcode_shared/db/models.py` |
| Enums / API payload shapes | `packages/shared/src/dcode_shared/schemas.py` |
| DDL, indexes, migration | `infra/migrations/versions/001_initial_schema.py` |
| Async engine / session factory | `packages/shared/src/dcode_shared/db/session.py` |
| Redis key conventions | `packages/shared/src/dcode_shared/cache.py` |
| Retrieval / graph SQL | `apps/api/src/dcode_api/routes/internal.py` |
| Write path (indexing) | `apps/worker/src/dcode_worker/stages/*` + `pipeline.py` |

---

## 1. What the database stores

Dcode indexes one Git repository into **two complementary retrieval surfaces**
plus a small registry:

- **Registry** — `repos`: one row per submitted repository and its indexing state.
- **Semantic surface** — `chunks`: AST-boundary code slices, each carrying a
  dense `embedding` vector (for semantic search) and a `tsv` full-text column
  (reserved; see §8). This is what `/internal/search` reads.
- **Structural surface** — `symbols` (graph nodes) + `edges` (graph edges): a
  static call/import/inherit/reference graph. This is what the graph endpoints
  (`find_definition`, `find_references`, `get_dependencies`, `get_dependents`,
  `get_file_outline`) read.

Everything is **multi-tenant by `repo_id`** (NFR-3): every child row carries the
owning `repos.id`, and all queries filter by it.

### Storage topology

| Store | Role | Durable? |
|---|---|---|
| **PostgreSQL 15 + pgvector** | `repos`, `chunks`, `symbols`, `edges` — vectors and graph in one instance | Yes (`postgres_data` volume) |
| **Redis 7** | Embedding cache, tool cache, query-SSE cache, live job-state snapshot | No (cache; TTLs per key) |
| **RabbitMQ** | Durable indexing job queue (`dcode.index_jobs`) — transport, not storage | Message-durable |
| **Repo workdir volume** | Cloned repository source on disk (`/tmp/dcode-workdirs/{repo_id}`) — read by the agent's filesystem tools | `repo_workdirs` volume |

Keeping vectors and the graph in a single PostgreSQL instance gives Dcode one
connection pool, one backup boundary, and one consistency model (see
[`Technical_Design.md`](Technical_Design.md), Key Design Decisions).

---

## 2. Entity model

```text
repos (1) ─────────< (N) chunks
   │                        ▲
   │                        │ chunk_id (SET NULL)
   └───────< (N) symbols ───┘
                  │
                  │ source_id / target_id
                  ▼
               (N) edges        edge: symbol ──edge_type──> symbol
```

- `repos 1─N chunks` (FK `chunks.repo_id`, `ON DELETE CASCADE`)
- `repos 1─N symbols` (FK `symbols.repo_id`, `ON DELETE CASCADE`)
- `symbols N─1 chunks` (FK `symbols.chunk_id`, `ON DELETE SET NULL`) — a symbol
  optionally links to the chunk that contains its definition.
- `edges` connect two `symbols` (`source_id`, `target_id`, both `ON DELETE CASCADE`).

Deleting a `repos` row cascades to all of its `chunks`, `symbols`, and `edges`.

---

## 3. Enum types

Four PostgreSQL `ENUM` types back the schema. Their literals must match the
`StrEnum`s in `schemas.py`.

| Enum | Values | Used by |
|---|---|---|
| `repo_status` | `queued`, `cloning`, `parsing`, `embedding`, `graphing`, `ready`, `failed` | `repos.status` |
| `chunk_type` | `function`, `method`, `class`, `module_doc` | `chunks.chunk_type` |
| `symbol_kind` | `function`, `class`, `method`, `module` | `symbols.kind` |
| `edge_type` | `calls`, `imports`, `inherits`, `references` | `edges.edge_type` |

`repo_status` advances monotonically through the pipeline
(`queued → cloning → parsing → embedding → graphing → ready`) and only ever
jumps sideways to `failed`. A separate app-level `StageState`
(`pending`/`in_progress`/`done`/`failed`) exists only in the Redis job snapshot
and the status API — it is **not** a database column.

---

## 4. Table reference

### 4.1 `repos` — indexing registry

One row per submitted repository. Updated by the worker at every stage transition.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4()` | Primary key; returned to the client as `repo_id` |
| `url` | `TEXT` | no | — | Git URL (validated API-side: no localhost/private IPs) |
| `commit_sha` | `TEXT` | yes | — | Set once clone resolves `HEAD` |
| `status` | `repo_status` | no | `queued` | Current pipeline state |
| `progress` | `INTEGER` | no | `0` | 0–100 |
| `error` | `TEXT` | yes | — | Failure reason when `status = failed` |
| `created_at` | `TIMESTAMP` | no | `now()` | DB-managed |
| `updated_at` | `TIMESTAMP` | no | `now()` (on update `now()`) | DB-managed |

### 4.2 `chunks` — semantic retrieval surface

One row per AST-boundary code slice: a module docstring, a top-level function, a
class, or a method. This is the searchable unit.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4()` | Primary key |
| `repo_id` | `UUID` | no | — | FK → `repos.id` `ON DELETE CASCADE` |
| `file_path` | `TEXT` | no | — | Repo-relative path, e.g. `src/requests/auth.py` |
| `chunk_type` | `chunk_type` | no | — | `function`/`method`/`class`/`module_doc` |
| `parent_symbol` | `TEXT` | yes | — | Enclosing class for methods; `NULL` otherwise |
| `symbol_name` | `TEXT` | no | — | Short name, e.g. `HTTPBasicAuth`, `send` |
| `signature` | `TEXT` | yes | — | Full def/class header rebuilt via `ast.unparse` (normalized to one line) |
| `start_line` | `INTEGER` | no | — | 1-based; excludes decorator lines (uses `node.lineno`) |
| `end_line` | `INTEGER` | no | — | 1-based, inclusive |
| `imports` | `JSONB` | no | `[]` | Module-level imports + imports found inside the node |
| `content` | `TEXT` | no | — | Verbatim source slice (capped at `max_chunk_chars`, default 20 000, with a `... [truncated]` marker) |
| `embedding` | `VECTOR(N)` | yes | — | Dense vector; `N = EMBEDDING_DIM` **fixed at migration time** (see §13/§17) |
| `tsv` | `TSVECTOR` | yes | — | Full-text column — **currently never populated** (see §8) |

### 4.3 `symbols` — graph nodes

One row per definition (module, class, function, method). These are the nodes of
the call graph and the target of `find_definition` / `get_file_outline`.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4()` | Primary key |
| `repo_id` | `UUID` | no | — | FK → `repos.id` `ON DELETE CASCADE` |
| `qualified_name` | `TEXT` | no | — | Dotted path, e.g. `src.requests.auth.HTTPBasicAuth.__call__` |
| `kind` | `symbol_kind` | no | — | `function`/`class`/`method`/`module` |
| `file_path` | `TEXT` | no | — | Defining file |
| `line` | `INTEGER` | no | — | Definition line (`module` symbols use line 1) |
| `chunk_id` | `UUID` | yes | — | FK → `chunks.id` `ON DELETE SET NULL`; links a symbol to its code chunk |

`qualified_name` is **unique per repo** (`ix_symbols_repo_qname_unique`).

### 4.4 `edges` — graph edges

One row per directed relationship between two symbols.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4()` | Primary key |
| `repo_id` | `UUID` | no | — | FK → `repos.id` `ON DELETE CASCADE` |
| `source_id` | `UUID` | no | — | FK → `symbols.id` `ON DELETE CASCADE` (the "from" symbol) |
| `target_id` | `UUID` | no | — | FK → `symbols.id` `ON DELETE CASCADE` (the "to" symbol) |
| `edge_type` | `edge_type` | no | — | `calls`/`imports`/`inherits`/`references` |
| `source_line` | `INTEGER` | no | — | Line in the source symbol where the relationship occurs |

**Edge-type semantics:**

| `edge_type` | Meaning | Produced by | Consumed by |
|---|---|---|---|
| `calls` | source calls target (`foo()`, `self.m()`, `alias.attr()`) | graph stage | `find_references` |
| `imports` | source module imports target module | graph stage | `get_dependencies`, `get_dependents` |
| `inherits` | source class inherits target class | graph stage | (queryable via SQL; no dedicated endpoint yet) |
| `references` | source uses target as a value, not called (`x = Cls`, annotations, `isinstance`) | graph stage | `find_references` |

---

## 5. Index reference

Created in `001_initial_schema.py`.

| Index | Table | Definition | Purpose |
|---|---|---|---|
| PK (implicit) | all | `(id)` | Primary key |
| `ix_chunks_repo_file` | `chunks` | `(repo_id, file_path)` btree | Scope + file-outline scans |
| `ix_chunks_embedding_hnsw` | `chunks` | `hnsw (embedding vector_cosine_ops)` | Dense (cosine) ANN search |
| `ix_chunks_tsv_gin` | `chunks` | `gin (tsv)` | Full-text search — **idle** (`tsv` unpopulated, see §8) |
| `ix_symbols_repo_qname_unique` | `symbols` | `(repo_id, qualified_name)` **unique** | Symbol resolution + uniqueness |
| `ix_edges_source` | `edges` | `(repo_id, source_id, edge_type)` | Forward traversal (dependencies, calls out) |
| `ix_edges_target` | `edges` | `(repo_id, target_id, edge_type)` | Reverse traversal (references, dependents) |

---

## 6. Multi-tenancy & referential integrity

- **Isolation:** every child row carries `repo_id`; every retrieval/graph query
  filters `WHERE repo_id = …`. There is no cross-repo query path.
- **Cascade:** deleting a `repos` row removes all its `chunks`, `symbols`, and
  `edges` (`ON DELETE CASCADE`). Deleting a `chunks` row nulls the referencing
  `symbols.chunk_id` (`ON DELETE SET NULL`) rather than deleting the symbol.
- **Re-indexing is full-replace per repo:** the worker deletes and rewrites all
  `chunks`, then all `symbols`/`edges`, so re-indexing the same repo is
  idempotent (see §11).

---

## 7. The two surfaces at a glance

| | Semantic surface | Structural surface |
|---|---|---|
| Tables | `chunks` | `symbols` + `edges` |
| Answers | "code about X", "where is `validate_token`" | "who calls X", "what does M import", "outline of file F" |
| Mechanism | dense vector (`embedding`) + sparse keyword | graph traversal over typed edges |
| Endpoint | `/internal/search` | `find_definition` / `find_references` / `get_dependencies` / `get_dependents` / `get_file_outline` |

---

## 8. Semantic surface details (`chunks.embedding`, `chunks.tsv`)

- **`embedding`** — dense vector, cosine ANN via the HNSW index. Written by the
  worker's embed stage. Under `EMBEDDING_MODEL=stub` the vectors are all-zeros
  and the API's query-side embedder returns `None`, so **dense search is inert
  and hybrid degrades to sparse** (this is why the checked-in eval shows
  B2 = B3 = B4; see `Final_Report.md`). Real vectors require the embedding
  sidecar (see [`Sidecar_Smoke.md`](Sidecar_Smoke.md)).
- **`tsv`** — declared with a GIN index, **but never populated**: the embed
  stage does not write `tsv`, and there is no trigger or generated column. The
  API's "sparse" search does **not** use `tsv` either — it runs
  `content/symbol_name/file_path ILIKE '%term%'` with a hand-tuned additive
  ranking (`_chunk_rank` in `internal.py`). The full-text infrastructure is
  currently dormant. (Wiring real BM25/`tsv` is tracked in the backlog.)

### `/internal/search` modes

| Mode | Path |
|---|---|
| `sparse` | `ILIKE` candidates → `_chunk_rank` heuristic |
| `dense` | pgvector `cosine_distance` on `embedding` (empty under stub → falls back to sparse) |
| `hybrid` | sparse + dense → weighted RRF (`dense:sparse = 2:1`, `k = 60`) → reranker (identity when reranker is stub) |

---

## 9. Structural surface details + endpoint→SQL mapping

Each internal graph endpoint is a thin SQL query. Symbol resolution matches an
exact `qualified_name`, else a suffix `.<name>` match.

| Endpoint | Semantics | Underlying query (simplified) |
|---|---|---|
| `find_definition?symbol=X` | where is X defined | `SELECT * FROM symbols WHERE repo_id=? AND (qualified_name = X OR qualified_name LIKE '%.X')` |
| `find_references?symbol=X` | who calls/references X | resolve X → `SELECT src FROM symbols src JOIN edges e ON e.source_id=src.id WHERE e.edge_type IN ('calls','references'[,'imports' if module]) AND e.target_id IN (resolved)` |
| `get_dependencies?module=M` | what M imports | resolve M (kind=module) → `edges` where `edge_type='imports' AND source_id IN (M)` → target symbols |
| `get_dependents?module=M` | who imports M | resolve M (kind=module) → `edges` where `edge_type='imports' AND target_id IN (M)` → source symbols |
| `get_file_outline?path=P` | symbols in file P | `SELECT * FROM symbols WHERE repo_id=? AND file_path=P ORDER BY line` |

See the copy-paste SQL equivalents in §15.

---

## 10. Redis keyspace

Redis is a cache and live-state store, not durable truth. All keys are built by
`cache.py` — never format keys inline.

| Key pattern | Contents | TTL |
|---|---|---|
| `embed:{model_id}:{sha256(text)}` | Cached embedding vector for a chunk's content | none (forever) |
| `tool:{tool_name}:{repo_id}:{sha256(args)[:16]}` | Cached agent tool result | 24 h (`tool_cache_ttl_seconds`) |
| `query:{repo_id}:{sha256(query)[:32]}` | Cached SSE byte stream for a query (non-error only) | 1 h (`query_cache_ttl_seconds`) |
| `job:{repo_id}` | Live job snapshot: `{status, progress, stages{}, error, warnings}` | none while in progress; 7 d (`job_state_ttl_seconds`) once complete |

The status endpoint (`GET /repos/{id}/status`) reads `job:{repo_id}` for live
per-stage progress and warnings, falling back to the durable `repos` row.

---

## 11. Write path (how the index is populated)

The worker consumes a job (`{repo_id, url}`) and runs a monotonic state machine.
Each transition **dual-writes**: the `repos` row (Postgres) and the `job:{repo_id}`
snapshot (Redis).

| Stage (`repos.status`) | Runners | Tables written |
|---|---|---|
| `cloning` | `clone` | `repos` (`commit_sha`, status/progress) |
| `parsing` | `parse`, `chunk` | `repos` (status/progress); builds chunk objects in memory |
| `embedding` | `embed` | **`chunks`** (full replace: `DELETE WHERE repo_id` → bulk insert) |
| `graphing` | `graph` | **`symbols`** then **`edges`** (full replace: delete edges → delete symbols → insert symbols → flush → insert edges) |
| `ready` | — | `repos` (status=ready, progress=100) |

Key properties:

- **Ordering matters:** embed commits `chunks` **before** graph runs, so the
  graph stage can link `symbols.chunk_id` to the just-written chunks.
- **Full-replace = idempotent:** re-indexing a repo cleanly overwrites its rows.
  A worker crash → RabbitMQ redelivers the unacked job → re-runs cleanly.
- **Failure:** any stage error sets `repos.status='failed'` with `error` and the
  failed stage's `in_progress` progress %. A repo deleted mid-flight is discarded
  without failing the message (`handle_job` never raises).
- **Commit cadence:** ~9 `repos` commits per successful job (2 per stage + final).

---

## 12. Read path (who reads what)

- **API `/internal/*`** (read by the agent and the eval harness): reads
  `chunks` (search), `symbols` + `edges` (graph), and `repos` (existence check).
- **Agent groundedness check**: the only place the agent touches the DB directly —
  verifies each citation against `chunks` (a chunk whose `[start_line, end_line]`
  contains the cited line) and `symbols` (an exact `qualified_name`).
- **Status endpoint**: reads `repos` + the Redis `job:` snapshot.

---

## 13. Migrations & schema management

- Schema is created by **Alembic migration `001_initial_schema`**
  (`infra/migrations/`). `infra/postgres/init.sql` only does
  `CREATE EXTENSION IF NOT EXISTS vector` on first container boot.
- Apply migrations:

  ```bash
  make migrate           # docker compose exec api uv run alembic ... upgrade head
  # or directly:
  uv run alembic -c infra/migrations/alembic.ini upgrade head
  ```

- **`EMBEDDING_DIM` is baked into the `chunks.embedding` column at migration
  time** (`Vector(shared_settings.embedding_dim)`). The default is `1024` (stub);
  Jina v2 real embeddings are `768`. Changing the dimension after the first
  migrate requires rebuilding the volume:

  ```bash
  docker compose down -v && make migrate    # destroys local data
  ```

---

## 14. Connecting & inspecting with `psql`

```bash
# Start only Postgres (reuses the postgres_data volume)
docker compose up -d --wait postgres

# Interactive shell (user/db are both 'dcode' by default from .env)
docker compose exec postgres psql -U dcode -d dcode

# One-off query, non-interactive
docker compose exec -T postgres psql -U dcode -d dcode -c "SELECT count(*) FROM chunks;"
```

Useful `psql` meta-commands: `\dt` (list tables), `\d chunks` (describe a table +
its indexes), `\x` (expanded/vertical output for wide rows), `\q` (quit).

**Cautions:**

- **Never `SELECT *`** on `chunks` — `embedding` (hundreds of floats) and `tsv`
  flood the terminal. Always list explicit columns.
- The local dev volume may hold **multiple copies of the same repo** (each
  submission is a distinct `repos.id`). Scope queries to one repo, e.g.
  `WHERE repo_id = (SELECT id FROM repos ORDER BY created_at LIMIT 1)`.

---

## 15. SQL cookbook

These map directly to the app's own operations.

```sql
-- Registry overview + row counts
SELECT id, url, status, progress FROM repos;
SELECT 'chunks' t, count(*) FROM chunks
UNION ALL SELECT 'symbols', count(*) FROM symbols
UNION ALL SELECT 'edges',   count(*) FROM edges;

-- (= get_file_outline) symbols defined in one file
SELECT qualified_name, kind, line
FROM symbols
WHERE file_path = 'src/requests/auth.py'
ORDER BY line;

-- (= find_definition) where a symbol is defined
SELECT qualified_name, kind, file_path, line
FROM symbols
WHERE qualified_name LIKE '%.HTTPBasicAuth';

-- (= find_references) who calls a given function
SELECT s.qualified_name AS caller, t.qualified_name AS callee, e.source_line
FROM edges e
JOIN symbols s ON s.id = e.source_id
JOIN symbols t ON t.id = e.target_id
WHERE e.edge_type = 'calls'
  AND t.qualified_name LIKE '%.send';

-- (= get_dependencies) what a module imports
SELECT s.qualified_name AS importer, t.qualified_name AS imported
FROM edges e
JOIN symbols s ON s.id = e.source_id
JOIN symbols t ON t.id = e.target_id
WHERE e.edge_type = 'imports'
  AND s.file_path = 'src/requests/sessions.py';

-- Inspect a chunk's raw source (content = original code)
SELECT file_path, symbol_name, content
FROM chunks
WHERE symbol_name = 'HTTPBasicAuth';

-- (= sparse search, approx) keyword scan over code
SELECT file_path, symbol_name, start_line, end_line
FROM chunks
WHERE content ILIKE '%Authorization%'
LIMIT 20;

-- Distributions
SELECT chunk_type, count(*) FROM chunks GROUP BY chunk_type ORDER BY 2 DESC;
SELECT edge_type,  count(*) FROM edges  GROUP BY edge_type;
SELECT file_path, count(*) AS symbols FROM symbols GROUP BY file_path ORDER BY 2 DESC LIMIT 10;
```

---

## 16. Vector similarity queries (pgvector)

The `embedding` column is only meaningful through vector distance operators, not
plain text. pgvector provides:

| Operator | Distance | Matches the HNSW index? |
|---|---|---|
| `<=>` | cosine distance | **Yes** (`vector_cosine_ops`) |
| `<->` | L2 (Euclidean) | no |
| `<#>` | negative inner product | no |

To rank chunks by semantic similarity you need a **query vector** (embed the
question with the same model). Example (`$1` = a 768-float literal
`'[0.01, -0.02, …]'::vector`):

```sql
SELECT file_path, symbol_name, 1 - (embedding <=> $1) AS cosine_similarity
FROM chunks
WHERE repo_id = :repo_id
ORDER BY embedding <=> $1     -- ascending distance = most similar first
LIMIT 10;
```

This mirrors `_search_dense_candidates` in `internal.py`. Under stub embeddings
there is no query vector (all-zero), so this path returns nothing useful — enable
the real sidecar first.

---

## 17. Operational gotchas

1. **Dimension trap.** `chunks.embedding` is fixed to whatever `EMBEDDING_DIM`
   was at migration time. A volume migrated at 768 will reject 1024-dim inserts
   (and vice-versa). Match `EMBEDDING_DIM` to the volume, or `down -v` + re-migrate.
2. **Stub vs real.** Stub embeddings are 1024-dim all-zeros and are treated as a
   cache miss on re-read (so stub mode does no effective caching and re-writes
   zeros each run). Real Jina v2 vectors are 768-dim non-zero floats — a quick
   `SELECT vector_dims(embedding), left(embedding::text, 20) FROM chunks LIMIT 1;`
   tells you which you have.
3. **`tsv` / GIN idle.** The full-text column and its index exist but are unused
   (§8). Do not assume keyword search hits the GIN index — it uses `ILIKE`.
4. **Graph v1 coverage.** Name-based static analysis only: no type inference, no
   MRO resolution for inherited `self.method()`, no nested-function/class symbols,
   decorators excluded from chunk/symbol line ranges. Treat the graph as
   best-effort static evidence.
5. **In-progress job state has no TTL.** A crashed job leaves a TTL-less
   `job:{repo_id}` key until a re-run completes it.
6. **Partial-failure window.** `chunks` (embed) and `symbols`/`edges` (graph)
   commit in separate transactions; a failure between them leaves the repo
   `failed` with new chunks but stale/missing graph rows until a successful re-index.

---

## 18. Current dev-volume snapshot

As inspected on the local `dcode_postgres_data` volume (for orientation; your
volume may differ):

| Item | Value |
|---|---|
| `repos` | 2 rows, both `https://github.com/psf/requests.git`, both `ready`, commit `f361ead047` |
| `chunks` | 1452 (726 per repo) |
| `symbols` | 1448 |
| `edges` | 736 — `calls` 606, `imports` 130 |
| `embedding` dims | **768** (real Jina v2 code embeddings, not stub) |
| Indexed | 2026-07-12 and 2026-07-13 |
| `chunk_type` split (one repo) | `method` 489, `function` 146, `class` 72, `module_doc` 19 |

Note: this data **predates the `inherits`/`references` edge work**, so `edges`
holds only `calls` + `imports`. Re-indexing with the current worker would add the
two newer edge types.

---

## Related documents

- [`Technical_Design.md`](Technical_Design.md) — architecture, API contracts, NFRs
- [`Sidecar_Smoke.md`](Sidecar_Smoke.md) — real embedding/reranker path + DB-dimension rebuild
- [`Final_Report.md`](Final_Report.md) — evaluation snapshot and the H1 decision
- [`Final_Report.md`](Final_Report.md) — remaining work (incl. `tsv`/BM25, richer graph edges)
