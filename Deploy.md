# Dcode Deployment Plan

## Document Scope

This document is the authority for taking Dcode online. It records the decisions
that were taken, the platform constraints that were verified, the invariants this
workstream may not break, and the work broken into reviewable slices.

It is deliberately **not** a second copy of the project backlog.
[`docs/en/Final_Report.md` § Outstanding Work](docs/en/Final_Report.md#outstanding-work)
remains the single list of what is unfinished in the *product*; this file covers
only what is unfinished in *getting it deployed*. When a deployment item is also
a product defect — most of them are — it is fixed here and struck from the
Outstanding Work list in the same PR, not tracked in two places.

| Read instead | For |
|---|---|
| [`docs/en/Final_Report.md`](docs/en/Final_Report.md) | The H1 verdict and the product backlog |
| [`docs/en/Technical_Design.md`](docs/en/Technical_Design.md) | Architecture, data model, API contracts |
| [`docs/en/Operations.md`](docs/en/Operations.md) | Running the stack locally, the real-model path, the eval harness |
| [`docs/en/Honesty_Constraints.md`](docs/en/Honesty_Constraints.md) | What the UI may assert |
| [`CLAUDE.md`](CLAUDE.md) | Session-level operational notes; §2 there points back here |

**Where this document and the code disagree, the code is the truth.** This file
is written from an approved plan, and plans outrun implementations. Verify before
relying on a claim here, and correct it when it is wrong.

**Status: PR 1 landed. PR 2 code complete, its pipeline run still pending.
PR 3–5 not started.** The pre-deployment state is frozen at tag
`v1.0-submission` (`a4612b8`). Nothing is deployed anywhere yet. Both hosted
model APIs have now been called from this codebase and the observed results are
in § 2.1 and § 6 PR 2, but no index has yet been built through them.

---

## 1. Decisions Taken

Recorded so a later reader can see what was chosen and what it ruled out.

| # | Decision | Date | Consequence |
|---|---|---|---|
| D-1 | **Run real models, served by third-party APIs**, not self-hosted sidecars | 2026-08-02 | No GPU/RAM budget for model serving; adds API keys, network dependency, and per-query cost. Makes § 2 possible. |
| D-2 | **Not publicly accessible.** A username/password gate sits between the landing page and the workbench | 2026-08-02 | Removes the anonymous-abuse surface (F-01, F-03 below) as a launch blocker. Landing and `/methodology` stay public; the product does not. |
| D-3 | **Deploy to Railway** | 2026-08-02 | TLS, certificates and a public hostname are solved by the platform. Two platform constraints in § 3 change the topology. |
| D-4 | **No fork. `Deploy` is a normal feature branch, merged back to `main` in slices** | 2026-08-02 | See § 5.5. |
| D-5 | **Explicit per-provider client classes**, not a generic OpenAI-compatible adapter layer | 2026-08-02 | Less code, and the wire contract of each provider is visible at its call site instead of hidden behind a shape that fits none of them exactly. Cost: adding a fourth provider later means writing a class, not setting a variable. Accepted. |
| D-6 | **One shared account**, not per-reviewer accounts | 2026-08-02 | No user table, no migration, no account lifecycle. The daily query cap in PR 3 is therefore per *session*, not per person, and a shared password cannot be revoked for one holder — rotate it instead. Adequate for a gated demo; not an authorization model. |

Decisions still open are in § 11.

---

## 2. Model Configuration Parity

**This constraint outranks every other item in this document.**

The project's central property is that the figures on `/methodology`, in
`README.md` and in `Final_Report.md` describe the system that is actually
running. All of them are generated from
`results/eval-h1-repeat3-2026-07-31/` by `scripts/sync_eval_artifacts.py`, and
`make check` fails if any displayed surface drifts from that directory.

That recorded run used exactly three models:

| Role | Model | Dimension |
|---|---|---|
| Embedding | `jinaai/jina-embeddings-v2-base-code` | 768 |
| Reranker | `BAAI/bge-reranker-v2-m3` | — |
| Synthesis | `gpt-4o-mini` | — |

All three are available as hosted APIs, so **D-1 can be satisfied without
changing a single model**:

| Role | Provider | Endpoint | Model id |
|---|---|---|---|
| Embedding | Jina AI | `https://api.jina.ai/v1/embeddings` | `jina-embeddings-v2-base-code` |
| Reranker | SiliconFlow | `https://api.siliconflow.cn/v1/rerank` | `BAAI/bge-reranker-v2-m3` |
| Synthesis | OpenAI | `https://api.openai.com/v1` (already supported via `OPENAI_BASE_URL`) | `gpt-4o-mini` |

**The rule.** The deployed configuration must use these three models. If a future
change substitutes any of them — a different embedding model, Jina's own
reranker instead of BGE, a different synthesis model — then the generated figures
no longer describe the deployed system, and one of two things must happen in the
same change:

1. the substitution is reverted; or
2. the landing page and `/methodology` carry an explicit statement that the
   deployed configuration differs from the evaluated one, naming the difference.

Silently deploying different models under the same numbers is the single most
damaging thing this workstream could do. It is not a performance question; it is
the same class of error as hand-typing a figure into prose.

**A caveat that is not resolved.** Serving the same weights through a provider's
API is not bit-identical to serving them locally: batching, quantization, and
model-version pinning are the provider's decisions, not ours. Parity of *model
identity* is achievable and required; parity of *output* is not guaranteed. This
does not affect the recorded verdict, which stays the authority and is not
regenerated. It does mean that **if the H1 suite is ever re-run through the API
providers, that is a new run directory with its own `provenance.json`, not a
refresh of the recorded snapshot.**

### 2.1 Verified against the live APIs, 2026-08-02

Both facts this plan depended on were observed rather than assumed, before any
client code was written.

- **Jina returns 768-dimensional vectors for `jina-embeddings-v2-base-code`.**
  Confirmed: `HTTP 200`, `dim=768`, `768/768` components non-zero. The dimension
  matches the recorded run, so no volume re-migration is implied.
- **SiliconFlow's rerank payload.** `{"model", "query", "documents",
  "return_documents"}` → `{"id", "meta", "results": [{"index", "document",
  "relevance_score"}]}`.

**And one thing neither the plan nor the documentation predicted: the response
does not come back in input order.** A three-document probe returned indices
`[1, 0, 2]`. Jina's embedding response likewise identifies each vector by
`index` rather than promising positional order. Both clients therefore place
results by index, and that is not defensive coding — zipping arrival order
against the input would attach the wrong embedding to a chunk, or score every
passage with another passage's relevance. Either produces no error, no log line,
and worse retrieval. This is what D-5 anticipated: neither API is
OpenAI-compatible in the part that actually matters.

### 2.2 SiliconFlow runs two platforms and they are not interchangeable

Found the hard way, recorded so nobody else spends the time.

| | `api.siliconflow.cn` | `api.siliconflow.com` |
|---|---|---|
| Rerankers offered | `BAAI/bge-reranker-v2-m3`, `Pro/BAAI/bge-reranker-v2-m3`, four Qwen3 variants | Qwen3 only — **no BGE** |
| A `.com` key against it | `401 "Api key is invalid"` | works |
| A `.cn` key against it | works | `401 "Token is invalid."` |

The failure is misleading in both directions: a wrong-region key reads as a bad
key, and a right-region key with the wrong model reads as `400 Model does not
exist`. **This project needs `.cn`,** because the model the evaluation used is
only there and § 2 does not permit substituting it. Using the `.com` platform
would have meant deploying a Qwen reranker under BGE's measured numbers.

---

## 3. Verified Platform Constraints (Railway)

Checked against Railway's documentation and community answers on **2026-08-02**.
Platform behaviour changes; re-verify before relying on any row.

| # | Constraint | Consequence for Dcode |
|---|---|---|
| R-1 | **A volume can be attached to only one service.** Railway recommends sharing data through Postgres/Redis rather than a volume. | `repo_workdirs` is written by `worker` and read by `agent` (`docker-compose.yml:103-104`, `:185-186`). The agent's `read_file` / `grep` / `list_directory` tools read that tree directly and raise `FileNotFoundError` without it (`apps/agent/src/dcode_agent/tools/common.py:38-43`). **Worker and agent must therefore share one Railway service.** |
| R-2 | **HTTP requests are closed after 5 minutes with no data transferred, and capped at ~15 minutes with keep-alive heartbeats.** | The agent emits no heartbeat frames and has **no overall request timeout** at all — `/internal/query` spawns a task and returns a stream immediately (`apps/agent/src/dcode_agent/main.py:94-109`), with per-hop timeouts only, giving a theoretical upper bound past 8 minutes. Needs both a heartbeat and a hard budget. |
| R-3 | **The default Postgres template does not ship pgvector**; the extension must exist at the server level. | Use a pgvector template for the Postgres service. `infra/postgres/init.sql` only runs `CREATE EXTENSION IF NOT EXISTS vector`, which fails if the binary is absent. |
| R-4 | **Private-network DNS names (`*.railway.internal`) change IP on every redeploy**, and legacy environments resolve IPv6-only. | nginx caches DNS resolution indefinitely with a literal `proxy_pass`. The frontend config must use `resolver [fd12::10] ipv6=on valid=1s;` plus a variable-form `proxy_pass`. |

R-1 is the only one that changes the architecture. R-2 through R-4 are configuration.

---

## 4. Target Topology

```
                       [ public HTTPS — Railway-managed TLS ]
                                       │
                          ┌────────────▼────────────┐
                          │ frontend                │   public
                          │ nginx + static bundle   │
                          └────────────┬────────────┘
                                       │ /api/*  →  api.railway.internal:8000
                          ┌────────────▼────────────┐
                          │ api                     │   private
                          │ FastAPI gateway + auth  │
                          └────────────┬────────────┘
                                       │ AGENT_URL → agent-worker.railway.internal:8001
                          ┌────────────▼────────────┐
                          │ agent-worker            │   private, owns the only volume
                          │ agent (:8001) + worker  │
                          └────────────┬────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
  Postgres (pgvector)              Redis                         RabbitMQ
```

Six services. The public surface is unchanged from the documented design: the
frontend is the only thing reachable, and it proxies `/api/*` to an API that is
still the only backend entry point. Merging `agent` and `worker` into one
container is a **platform workaround for R-1**, not an architectural revision —
the agent still exposes only `/internal/*` behind the internal API key, and the
worker still consumes from RabbitMQ.

---

## 5. Standing Constraints for This Workstream

These are invariants. A PR that breaks one should not merge, even if it works.

### 5.1 The local multi-container path must not regress

Every mode that works today must still work after this workstream:

| Mode | How it starts | Needs network / keys |
|---|---|---|
| stub | `make up` | no |
| Docker sidecars | `make up-embed` / `make up-rerank` | weights download on first run |
| host sidecars | `make embedding-host` + `make reranker-host` + `make up` | weights download on first run |
| **API providers (new)** | `make up` with `EMBEDDING_PROVIDER` / `RERANKER_PROVIDER` set | yes |

Concretely: `apps/embedding/`, `apps/reranker/`, the `embedding` / `reranker`
Compose profiles, `scripts/start-*-host.sh`, `HttpEmbeddingClient` and
`HttpRerankerClient` are all **untouched** by this workstream.

The one place this could be broken carelessly is R-1. The worker+agent merge is a
Railway-only entrypoint. `dcode_agent.main:app` and `dcode_worker.main` both keep
their own entrypoints (`infra/docker/agent.Dockerfile:22-24`,
`infra/docker/worker.Dockerfile:21`), and `docker-compose.yml` keeps two separate
containers sharing the volume. **Local Docker supports shared volumes; Railway
does not. That is a platform difference, not a code difference, and the local
path must not be degraded to match the constrained one.**

### 5.2 The provider switch is additive, not a replacement

`create_embedding_client()` (`packages/shared/src/dcode_shared/embedding.py:125-149`)
and `create_reranker_client()` (`packages/shared/src/dcode_shared/reranker.py:109-127`)
currently branch on one condition, `model == "stub"`. The API providers are a new
branch beside the existing sidecar branch, selected by an explicit
`EMBEDDING_PROVIDER` / `RERANKER_PROVIDER` whose default is `sidecar`. Existing
`.env` files, existing tests, and existing Compose invocations keep their current
behaviour with no edit.

### 5.3 CI stays keyless

`.github/workflows/ci.yml` currently requires no secrets. It must still require
none. Tests for the new clients mock the HTTP layer; they never call a live API.

### 5.4 Embedding configuration must be identical on `api` and `agent-worker`

The worker writes vectors at index time; the API embeds the query at search time.
They are separate processes reading the same settings. Setting the provider on
one and not the other produces **no error** — it produces Jina vectors in the
database being searched with a stub all-zero query vector
(`packages/shared/src/dcode_shared/embedding.py:37-38`), i.e. dense retrieval
silently returning noise. This is already latent in `docker-compose.prod.yml`,
where the `api` service has no embedding configuration at all (F-02).

The mitigation is not discipline. It is the readiness check in PR 5: compare the
configured `EMBEDDING_DIM` against the live `vector_dims` of `chunks.embedding`
at startup and report not-ready on a mismatch, rather than discovering it on the
first insert.

### 5.5 Branch and release policy

- No fork. `Deploy` is a feature branch; the work merges to `main` as the five
  PRs in § 6, each independently green under `make check`.
- Nothing lands on `main` that leaves it in a worse state than `v1.0-submission`.
- Secrets never enter the repository. `.gitignore:11-14` already covers `.env`,
  `.env.production`, `.env.local`; Railway environment variables are configured
  in the Railway dashboard, not in a committed file.
- `.env.production.example` stays committed and stays free of real values.

### 5.6 `docker-compose.prod.yml` is fixed, not deleted

`Final_Report.md` lists "a production-shaped Docker Compose package" as
delivered. Deleting it to make room for Railway would turn that into a false
claim. After this workstream there are two supported paths — self-hosted Compose
and hosted Railway — and the Compose path is where the Railway configuration gets
validated locally before it is pushed.

### 5.7 Displayed numbers are still generated, never typed

Unchanged from `CLAUDE.md`, restated because this workstream touches
configuration rather than results and the rule is easy to forget in that context:
no figure from `results/` may be hand-written into `Deploy.md`, the README, the
UI, or a Railway description.

---

## 6. Work Breakdown

Five PRs, in dependency order. Each is independently reviewable, independently
revertable, and must pass `make check` and `make frontend-build` on its own.

**Acceptance criteria are binding.** A PR is not done when the code is written;
it is done when its criteria are demonstrated, and honestly reported when they
are not.

### PR 1 — `fix/prod-compose-model-env` — **done**

Pure defect repair. Smallest, lands first, useful even if deployment never
happens.

| Item | Detail | Outcome |
|---|---|---|
| F-02 | Give every service the retrieval settings it reads. See the correction below — this was wider than "the `api` service". | done |
| F-11 | Reconcile the two documented Compose invocations: `README.md:324` used `-f docker-compose.prod.yml` alone; `.env.production.example:4-5` documented overlaying it on `docker-compose.yml`, which republishes Postgres, Redis and the RabbitMQ management UI to the host. | done — standalone form, and both files now say so |
| F-12 | Remove the dead `RERANKER_ENDPOINT=http://localhost:9999` default. | done — empty default, which fails loudly for a real model and is ignored by a stub |
| F-13 | `max_retries=12` against a hardcoded 300 s timeout (`embedding.py:19-20`) can occupy one batch of four chunks for roughly an hour while `prefetch_count=1` stalls the queue behind it. | **partially done** — the timeout is now env-tunable (`EMBEDDING_TIMEOUT_SECONDS`) instead of hardcoded; the *values* are unchanged, because the defaults are correct for a cold CPU sidecar and the hosted-API path they are wrong for does not exist until PR 2. PR 2 sets them. |

**Correction: F-02 was under-described in the original plan.** It was written as
"the `api` service has no embedding configuration". Reading what each service
actually reads showed all three were short:

| Service | Was missing |
|---|---|
| `api` | every retrieval setting — all twelve |
| `worker` | `EMBEDDING_ENDPOINT`, `EMBEDDING_BATCH_SIZE`, `EMBEDDING_MAX_RETRIES` — so it had a model and a dimension but no way to reach a service |
| `agent` | `RERANKER_MODEL`, `RERANKER_MAX_RETRIES`, `EMBEDDING_DIM`, and the synthesis knobs. It had `RERANKER_ENDPOINT` alone, which selects nothing: `create_reranker_client` returns `None` for a stub model whatever the endpoint says (`packages/shared/src/dcode_shared/reranker.py:119-120`) |

`EMBEDDING_DIM` also turned out to matter more widely than the migration.
`dcode_shared.db.models:128` binds the `chunks.embedding` column type to it at
**import time**, so every service that touches the ORM needs it correct, not just
the one that runs Alembic. It is now required in production (`${EMBEDDING_DIM:?…}`)
rather than defaulted, because a wrong value there is a re-index, not a slow query.

**Acceptance — met.**

1. `docker compose --env-file .env.production.example -f docker-compose.prod.yml config`
   resolves 12 retrieval variables on `api`, 6 on `worker`, 9 on `agent`, all
   mutually consistent. Observed.
2. Omitting `EMBEDDING_DIM` aborts the config with the reason attached rather
   than silently defaulting. Observed.
3. `make check` green: ruff, eslint, the eval-artifact drift check, mypy strict
   over 83 source files, 289 passed / 5 skipped in pytest, 73 frontend tests.
4. Three new tests in `packages/shared/tests/test_config_hardening.py` pin all
   of the above, and **each was confirmed to fail when its defect is put back** —
   a config test that has never been seen failing is not evidence of anything.

### PR 2 — `feat/managed-model-providers` — **code complete, pipeline run pending**

The capability behind D-1.

- Add `JinaApiEmbeddingClient` to `packages/shared/src/dcode_shared/embedding.py`.
  The sidecar contract is an unauthenticated `POST {endpoint}/embed` with
  `{"texts": [...]}` returning `{"embeddings": [[...]]}` (`embedding.py:87-90`);
  Jina's is an authenticated `POST /v1/embeddings` with `{"model", "input"}`
  returning `{"data": [{"index", "embedding"}]}`. **Results must be reordered by
  `index`, not trusted in arrival order.**
- Add the SiliconFlow reranker client to
  `packages/shared/src/dcode_shared/reranker.py`. Same shape of problem: the
  sidecar returns `{"scores": [...]}` in passage order (`reranker.py:54-61`);
  a rerank API returns scored results carrying their own index, which must be
  mapped back to input order before returning.
- Select with `EMBEDDING_PROVIDER` / `RERANKER_PROVIDER`, default `sidecar`
  (§ 5.2). Add `EMBEDDING_API_KEY` / `RERANKER_API_KEY`.
- Per D-5 these are **two concrete classes with the provider's own payload shape
  written out**, not a generic adapter parameterised by field names. Neither
  provider is OpenAI-compatible in the part that matters — the response carries
  per-item indices that must be mapped back — so a shared abstraction would have
  to model the difference anyway.
- Timeouts and retries appropriate to a hosted API, not to a cold local model.

**Acceptance — 1 met, 2 partially met, 3 met.**

1. **Met.** 21 tests over a mocked transport (`httpx.MockTransport`) cover
   index-based reordering, batching with order preserved across batch
   boundaries, dimension mismatch, short response, duplicated index,
   out-of-range index, auth header, non-retryable 401 surfacing on the first
   attempt, retryable 429 backing off, provider selection, missing-key errors,
   unknown-provider errors, and stub short-circuiting before the provider is
   consulted. No live calls (§ 5.3), and the backoff sleep is captured rather
   than waited out.

2. **Partially met.** The production client classes were exercised against both
   live APIs, and the observed values are recorded here:

   | Check | Observed |
   |---|---|
   | `JinaApiEmbeddingClient`, 5 inputs over 3 batches | 5 vectors, all `dim=768`, all non-zero, all distinct |
   | Cross-batch ordering | re-embedding input 2 alone lands `0.000000` from its batched slot; nearest other slot is `0.586` |
   | `SiliconFlowRerankerClient`, 3 passages | scores returned in input order; argmax is the `HTTPBasicAuth` passage for a credentials question |

   **What is not done: the full indexing pipeline has not been run through the
   hosted provider.** 726 chunks at batch 32 is roughly 23 requests, which is
   where rate limiting and the embed stage's Redis cache interaction would show
   up, and neither has been exercised. Until that runs, this PR proves the
   clients are correct, not that an index built through them is.

3. **Met.** `make check` green: ruff, eslint, the drift check, mypy strict over
   83 files, 310 passed / 5 skipped, 73 frontend tests. All four modes in § 5.1
   still resolve, and `sidecar` remains the default everywhere.

### PR 3 — `feat/auth-gate`

D-2. Also closes F-01 and F-03.

- `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
  Per D-6, **one shared account read from the environment** — no user table, no
  migration. The password is stored as a hash, never as plaintext in the repo or
  in a committed file. Signed, `HttpOnly`, `Secure`, `SameSite=Lax` cookie.
- A dependency on the `repos`, `query` and `inspector` routers
  (`apps/api/src/dcode_api/main.py:45-47`). `/healthz` stays open.
- Frontend `/login` route; `/workbench` checks the session and redirects on 401.
  `/` and `/methodology` remain public — they are the part meant to be read.
- F-05: disable `/docs`, `/redoc` and `/openapi.json` in production. They are
  public today and advertise the `/internal/*` surface.
- A per-session daily query cap. The login wall removes anonymous abuse; it does
  not remove a logged-in user looping a query against a metered API.

**Acceptance.** An unauthenticated request to each protected route returns 401.
`/`, `/methodology` and `/healthz` are reachable without a session. The
`/workbench` redirect is verified **by a human in a browser** — headless
screenshots do not work in this environment, and that limitation is not a reason
to claim the check passed.

### PR 4 — `feat/railway-deploy`

The only Railway-specific PR. Mostly additive files.

- R-1: a combined `agent` + `worker` entrypoint used **only** by the Railway
  service. `docker-compose.yml` is not touched (§ 5.1).
- R-2: SSE heartbeat frames (a `:` comment line on an interval below Railway's
  5-minute idle cut). The frontend parser already skips `:` lines
  (`apps/frontend/src/api/client.ts:142-144`), so no frontend change is required.
  Plus an overall agent request budget that expires inside Railway's window and
  emits a clean `error` event rather than being cut by the platform.
- R-4 and static-serving fixes in `apps/frontend/nginx.conf`: variable-form
  `proxy_pass` with `resolver`, an explicit `proxy_read_timeout` for the SSE
  path, `listen` on the platform-assigned port, **gzip on** (verified off by
  default in `nginx:1.27-alpine`; the built main chunk is 752.53 kB, 226.74 kB
  gzipped), and long-lived cache headers on hashed assets.
- A root `.dockerignore` and one for `apps/frontend` (the frontend build context
  currently ships 227 MB of `node_modules` to the daemon; the root context is
  391 MB).
- F-09: `GET /api/v1/repos` so the workbench can list indexed repositories.
  Today the switcher reads `localStorage` only
  (`apps/frontend/src/lib/recentRepos.ts:8`) and there is no default repository,
  so a first-time visitor on a new device sees an empty workbench.

**Acceptance.** A live deployment reachable over HTTPS; login works; one indexed
repository is selectable; a query streams to completion with verified citations;
clicking a citation opens real indexed source. Every one of those is confirmed by
a human in a browser and reported with what was actually seen.

### PR 5 — `fix/audit-followups`

Findings that are not launch blockers but should not ship unaddressed.
See the register in § 7 for F-04, F-06, F-07, F-08, F-10, F-14, F-15.

**Acceptance.** Each item either fixed with a test, or explicitly deferred in
this document with a reason. Silence is not an outcome.

---

## 7. Findings Register

Every row carries a `file:line` so it can be checked rather than believed.

**Verification column.** `direct` — confirmed in this session by reading the file,
running the command, or resolving the Compose config. `audit` — reported by a
code-audit pass with a citation, not independently re-checked. Treat `audit` rows
as leads to verify when the PR touches them, not as established fact.

| # | Finding | Where | Severity | PR | Verified |
|---|---|---|---|---|---|
| F-01 | No authentication of any kind on `/api/v1/*`; no user or tenant concept, so any caller can read any indexed repo by `repo_id` | `apps/api/src/dcode_api/main.py:45-47` | blocker | 3 | audit |
| F-02 | ~~The `api` service in the production Compose file has no embedding or reranker configuration~~ **— fixed in PR 1, and it was wider than this row said: `worker` and `agent` were short too. See § 6 PR 1.** | `docker-compose.prod.yml` | blocker | 1 | **direct** |
| F-03 | No rate limiting, no request-size limit, no quota. `QueryRequest.query` has `min_length` but no `max_length` | `packages/shared/src/dcode_shared/schemas.py:132` | blocker | 3 | audit |
| F-04 | `INTERNAL_API_KEY` defaults to a literal published in this repository, with no startup guard outside Compose's `:?` operator — and Railway sets variables per service, so that operator does not protect the deployment | `packages/shared/src/dcode_shared/settings.py:33` | high | 5 | audit |
| F-05 | `/docs`, `/redoc` and `/openapi.json` are publicly served and advertise the `/internal/*` surface | `apps/api/src/dcode_api/main.py:31-35` | high | 3 | audit |
| F-06 | SSRF: repository URL validation rejects literal private IPs but has no host allowlist and no resolution check, so a hostname resolving to an internal address passes | `apps/api/src/dcode_api/routes/repos.py:203-224` | high | 5 | audit |
| F-07 | The agent tool cache key omits `index_revision`, so re-indexing a repository does not invalidate cached tool results for up to 24 h | `apps/agent/src/dcode_agent/graph.py:119` | high | 5 | audit |
| F-08 | Cloned workdirs are never cleaned up, for any repository, ever. On a fixed Railway volume this is unbounded growth | `apps/worker/src/dcode_worker/stages/clone.py:17-22` | high | 5 | audit |
| F-09 | No repository list endpoint; the switcher reads `localStorage` only and there is no default repository | `apps/frontend/src/lib/recentRepos.ts:8` | high | 4 | **direct** |
| F-10 | `/healthz` returns `ok` unconditionally — it reports healthy with every dependency down. No readiness probe exists | `apps/api/src/dcode_api/main.py:51-54` | medium | 5 | audit |
| F-11 | ~~The two documented production Compose invocations disagree; one of them republishes Postgres, Redis and the RabbitMQ UI~~ **— fixed in PR 1.** | `README.md`, `.env.production.example` | medium | 1 | **direct** |
| F-12 | ~~`RERANKER_ENDPOINT` defaults to a dead loopback address in the production template~~ **— fixed in PR 1, pinned by a test.** | `docker-compose.prod.yml`, `.env.production.example` | medium | 1 | **direct** |
| F-13 | Embedding retries are 12 attempts against a 300 s timeout; with `prefetch_count=1` one bad batch stalls the entire indexing queue. **Knob added in PR 1 (`EMBEDDING_TIMEOUT_SECONDS`); the values are set in PR 2, where the path that needs them exists.** | `packages/shared/src/dcode_shared/embedding.py:19-20` | medium | 1 → 2 | audit |
| F-14 | `git clone` receives the repository URL with no `--` separator, so a URL beginning with `-` is parsed as an option. Gateway validation is the only defence; the worker has none | `apps/worker/src/dcode_worker/stages/clone.py:22` | medium | 5 | audit |
| F-15 | The `grep` tool runs `rg` with no timeout and buffers all output in memory; the pure-Python fallback compiles a user-supplied regex with no timeout | `apps/agent/src/dcode_agent/tools/grep.py:44-58`, `:79-101` | medium | 5 | audit |
| F-16 | nginx serves the bundle uncompressed — gzip is commented out in the base image and not enabled in the site config. Main chunk 752.53 kB / 226.74 kB gzipped | `apps/frontend/nginx.conf` | low | 4 | **direct** |
| F-17 | No `.dockerignore` anywhere; the frontend build context ships 227 MB of `node_modules` | repository root | low | 4 | **direct** |
| F-18 | Model sidecars download weights from Hugging Face at runtime with no cache volume | `infra/docker/embedding.Dockerfile`, `infra/docker/reranker.Dockerfile` | low | — | **direct** |

F-18 is recorded but **not scheduled**: D-1 removes the sidecars from the
deployment path, so it only affects local Docker-profile use. It is left as a
known cost of that mode rather than fixed speculatively.

### Already correct, recorded so nobody "fixes" it

- SSE anti-buffering headers are set on both hops — `Cache-Control: no-cache` and
  `X-Accel-Buffering: no` at `apps/api/src/dcode_api/routes/query.py:43-44` and
  `apps/agent/src/dcode_agent/main.py:108`. R-2 is a platform *timeout*, not a
  buffering problem, and does not indicate these are wrong.
- Agent path handling is sound: `normalize_repo_relative_path` rejects absolute
  and `..`-escaping paths and the resolved path is re-checked against the root
  (`apps/agent/src/dcode_agent/tools/common.py:46-76`).
- In the production topology the `api` service publishes no host port and nginx
  proxies only `location /api/`, so `/internal/*` is not reachable from outside.

---

## 8. New Environment Variables

Added by this workstream. Every one defaults to current behaviour.

| Variable | Default | Read by | Purpose |
|---|---|---|---|
| `EMBEDDING_PROVIDER` | `sidecar` | api, worker | `sidecar` \| `jina_api` |
| `EMBEDDING_API_KEY` | `""` | api, worker | Required when the provider is not `sidecar` |
| `RERANKER_PROVIDER` | `sidecar` | api | `sidecar` \| `siliconflow` |
| `RERANKER_API_KEY` | `""` | api | Required when the provider is not `sidecar` |
| `AUTH_USERNAME` | — | api | Demo account name |
| `AUTH_PASSWORD_HASH` | — | api | Hash, never a plaintext password |
| `AUTH_SESSION_SECRET` | — | api | Cookie signing key |
| `AUTH_DAILY_QUERY_LIMIT` | (to set) | api | Per-session spend guard |
| `AGENT_REQUEST_BUDGET_SECONDS` | (to set) | agent | R-2 hard ceiling |
| `SSE_HEARTBEAT_SECONDS` | (to set) | api, agent | R-2 keep-alive interval |
| `DOCS_ENABLED` | `false` in production | api | F-05 |

`EMBEDDING_DIM` keeps its existing meaning and its existing trap: it is fixed
into the pgvector column at migration time. Changing it requires a fresh volume.
Switching providers is now a one-line edit, which makes that trap *easier* to
trigger than it was when it required starting a sidecar.

`JUDGE_MODEL` is passed by both Compose files and defined in settings but is
referenced by no code. It is left alone here; removing dead configuration is a
product decision, not a deployment one.

---

## 9. Cost

Order-of-magnitude only. No figure here is measured, and none should be quoted
as if it were.

- **Embedding** is paid once per index, not per query. Jina offers a free tier,
  and the corpus is small — the chunk count of the indexed `psf/requests`
  snapshot is recorded in [`docs/en/Operations.md`](docs/en/Operations.md), not
  restated here.
- **Reranking** runs per query over a candidate list capped by
  `RERANKER_CANDIDATE_LIMIT` (default 16).
- **Synthesis** is one `gpt-4o-mini` call per query, bounded by
  `SYNTHESIS_MAX_TOKENS` (default 700) with an input side bounded by a 10-item
  evidence budget. A follow-up question costs a second, smaller call.
- **Railway** bills six services by usage; an idle gated demo is small.

The real exposure is not the unit price — it is an unbounded number of calls.
D-2 removes anonymous callers; `AUTH_DAILY_QUERY_LIMIT` bounds authenticated
ones. Both are required.

---

## 10. Verification Checklist

Two limits of this environment apply to every claim made about this work, and
neither is a reason to soften a report:

- **Headless screenshots do not work.** Anything visual is confirmed by a human
  in a real browser, or it is reported as unconfirmed. Say what to look at.
- **There is no automated end-to-end test spanning browser and live backend.**

Before calling the deployment done:

| # | Check | How |
|---|---|---|
| 1 | Vectors in the deployed database are 768-dimensional and non-zero | `SELECT vector_dims(embedding), left(embedding::text, 20) FROM chunks LIMIT 1;` |
| 2 | The reranker is actually reordering, not passing through | Compare `score_components` on a query with and without rerank |
| 3 | `api` and `agent-worker` agree on embedding configuration | § 5.4 readiness check reports ready |
| 4 | A query streams to completion without being cut | Watch a full run; confirm no truncation at 5 minutes (R-2) |
| 5 | Citations are verified and clickable, and open real indexed source at the cited line | Human, in a browser |
| 6 | Call-graph neighbours are clickable and chain | Human, in a browser |
| 7 | Unauthenticated access to `/workbench` and to each protected route is refused | Private window |
| 8 | `/` and `/methodology` load without a session, and their figures match `results/` | `python3 scripts/sync_eval_artifacts.py --check` |
| 9 | The four local modes in § 5.1 all still start | Locally, after the final PR |

---

## 11. Open Questions

Carried here rather than answered by assumption.

1. **Team ownership.** `README.md` assigns "infrastructure, deployment" to a
   different team member, and `origin` carries four `yuxin_*` branches. This plan
   should be reconciled with them before PR 4. *Not resolved.* Pushing `Deploy`
   and `v1.0-submission` makes it visible to them, which is the point.
2. **Long-term fix for R-1.** Merging agent and worker is a workaround. The
   durable answer is to stop reading repository source from a shared filesystem —
   store file contents in Postgres and have the agent's file tools read from
   there. That is a migration plus three tool rewrites, deliberately out of scope
   here. *Deferred, recorded.*
