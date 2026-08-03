# Railway service configuration

Three `*.toml` files here, one per service that builds from this repository.
The three data services (Postgres, Redis, RabbitMQ) come from Railway templates
and need no file.

**Nothing here has been deployed.** These were written from the code, and the
sequence in [`Deploy.md` §10.2](../../Deploy.md) is the intended one rather than
a recorded one. Correct both against what actually happens.

## Wiring each service

| Service | Config as Code path | Root Directory | Public domain |
|---|---|---|---|
| `frontend` | `/infra/railway/frontend.toml` | *(empty)* | **yes — the only one** |
| `api` | `/infra/railway/api.toml` | *(empty)* | no |
| `agent-worker` | `/infra/railway/agent-worker.toml` | *(empty)* | no |

The Config as Code path is **not** relative to Root Directory, so it is absolute
from the repository root. Leave Root Directory empty: every image here builds
from the repository root, including the frontend — it used to build from
`apps/frontend` and was changed precisely so this table has no exception in it.

`agent-worker` needs **one volume**, mounted at whatever `WORKDIR_BASE` says
(`/tmp/dcode-workdirs` by default). Without it the cloned checkout is lost on
every redeploy, and the agent's `read_file` / `grep` / `list_directory` fail for
every repository until it is re-indexed. Search and the call graph keep working,
because they read Postgres — which is exactly the confusing half-failure the
volume prevents.

## Variables

Two rules first, because both fail silently.

**`EMBEDDING_*` and `RERANKER_*` must agree across `api` and `agent-worker`.**
The API embeds the search query, the worker embeds the corpus, the agent reranks
its own evidence. Configuring one and not the other produces no error — it
produces real vectors in the database being searched with a stub all-zero query
vector (`Deploy.md` §5.4).

**A `$` in a value is safe in the Railway dashboard** (it is not an env file) but
**not** in a bulk import or a committed env file, where `$VAR` is expanded. A
password hash lost three of its four segments that way and every login failed
forever while the service reported healthy (`Deploy.md` §2.3). The hash format
avoids `$` now; a hand-picked Postgres password still can.

### `api`

| Variable | Value |
|---|---|
| `HOST` | `::` — **required.** Railway's private network is IPv6; a service bound to `0.0.0.0` there is reachable by nothing |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}`, rewritten to the `postgresql+asyncpg://` scheme |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `RABBITMQ_URL` | from the RabbitMQ service |
| `AGENT_URL` | `http://agent-worker.railway.internal:8001` |
| `INTERNAL_API_KEY` | 32+ characters. The API refuses to start on the published placeholder |
| `AUTH_ENABLED` | `true` |
| `AUTH_USERNAME`, `AUTH_PASSWORD_HASH`, `AUTH_SESSION_SECRET` | `python -m dcode_api.hash_password` generates the hash and prints a secret command |
| `AUTH_COOKIE_SECURE` | `true` — Railway serves HTTPS |
| `AUTH_DAILY_QUERY_LIMIT` | a number. The login wall stops anonymous callers, not a signed-in loop over three metered APIs |
| `DOCS_ENABLED` | `false` |
| `EMBEDDING_DIM` | `768` for `jina-embeddings-v2-base-code`. **Fixed into the column by the migration; changing it later means a new volume** |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_ENDPOINT` / `EMBEDDING_API_KEY` | `jina_api` / `jina-embeddings-v2-base-code` / `https://api.jina.ai/v1` / your key |
| `EMBEDDING_BATCH_SIZE`, `EMBEDDING_MAX_RETRIES`, `EMBEDDING_TIMEOUT_SECONDS` | `32`, `3`, `30`. The defaults are sized for a cold CPU sidecar and would hold one batch for an hour against an API |
| `RERANKER_PROVIDER` / `RERANKER_MODEL` / `RERANKER_ENDPOINT` / `RERANKER_API_KEY` | `siliconflow` / `BAAI/bge-reranker-v2-m3` / `https://api.siliconflow.cn/v1` / your key. **The `.cn` platform** — `.com` serves no BGE and the keys are not interchangeable (`Deploy.md` §2.2) |
| `REPO_URL_ALLOWED_HOSTS` | optional, e.g. `github.com`. The only rule in the URL check that states what is *allowed*, and the available mitigation for DNS rebinding |

### `agent-worker`

Same `EMBEDDING_*` / `RERANKER_*` / `INTERNAL_API_KEY` / `DATABASE_URL` /
`REDIS_URL` / `RABBITMQ_URL` values as `api`, plus:

| Variable | Value |
|---|---|
| `HOST` | `::` |
| `RETRIEVAL_BASE_URL` | `http://api.railway.internal:8000` |
| `WORKDIR_BASE` | the volume's mount path |
| `WORKDIR_MAX_REPOS` | a number the volume can hold. `0` never evicts, which is how the volume fills; read `Deploy.md` §6 PR 5 for what eviction costs |
| `SYNTHESIS_MODEL`, `OPENAI_API_KEY` | `gpt-4o-mini` and your key, to get prose answers rather than the rule-based template |
| `AGENT_REQUEST_BUDGET_SECONDS`, `SSE_HEARTBEAT_SECONDS` | `240`, `20`. Both sized against the platform's request limits (`Deploy.md` R-2) |

`EMBEDDING_DIM` is needed here too. The agent does not read it directly, but
`dcode_shared.db.models` binds the `chunks.embedding` column type to it at
import time.

### `frontend`

| Variable | Value |
|---|---|
| `API_UPSTREAM` | `http://api.railway.internal:8000` — match your actual service name |
| `DNS_RESOLVER` | Railway's internal resolver address |

`PORT` is injected; do not set it.

## Order

Postgres, Redis and RabbitMQ first. Then `api` — its `preDeployCommand` runs the
migration, so `EMBEDDING_DIM` must be right **before** the first deploy of it.
Then `agent-worker`, then `frontend`.

Then walk the checklist in `Deploy.md` §10. The rows that need a browser need a
browser.
