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

**Status: PR 1–5 landed. Nothing is deployed yet** — every remaining item is
in § 10.2 and needs a Railway account. The pre-deployment state
is frozen at tag `v1.0-submission` (`a4612b8`). Nothing is deployed anywhere
yet. Both hosted model APIs have been exercised end to end from a running local
stack — see § 2.1 and § 6 PR 2 for the observed values — but **no index has been
built through them**, so the indexing side of the hosted path is still unproven.

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

### PR 2 — `feat/managed-model-providers` — **done, with one gap named below**

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

   The **running stack** was then switched to both hosted providers
   (`docker compose up -d --build api agent`, since the images are not
   live-mounted) and queried against the existing 768-dimension index — the one
   the *sidecar* wrote. That combination is the parity claim under test: a query
   vector from Jina's API searching vectors produced by the local model.

   | Check | Result |
   |---|---|
   | `mode=dense`, the zero-keyword-overlap query from Operations.md | **identical ranking**, same five chunks in the same order; cosine differs in the third decimal (0.5155 → 0.5182) |
   | `mode=hybrid` | same five chunks; the top two swap, and they were **tied at 0.0042** in the baseline — the hosted run broke the tie 0.0043/0.0042. A tie broken differently is not a behaviour change |
   | Reranker identity | hosted BGE returns scores in the same magnitude band as the local BGE sidecar (~0.004). The Qwen reranker on SiliconFlow's other platform returned ~0.64 on a comparable query, so the band is circumstantial evidence that the model is the one asked for |
   | Full agent path, `POST /api/v1/query` | 3 tool calls (`search_code` → `get_call_neighbors` → `read_file`), 2 citations, **both verified**, groundedness `1.0` |
   | Against the documented run | reproduces Operations.md *Verified Current Path — 2026-07-30* citation for citation: `sessions.py:186` and `sessions.py:557` |

   The third-decimal drift is exactly the caveat § 2 records: same weights,
   different serving stack, not bit-identical. It is visible and it does not
   move the ranking.

   **What is still not done: no index has been built through the hosted
   provider.** The verification above is query-side. 726 chunks at batch 32 is
   roughly 23 requests, which is where rate limiting and the embed stage's Redis
   cache interaction would appear, and neither has been exercised. That is
   deliberate — re-indexing would replace the verified reference index — and it
   will happen naturally at the first Railway index. Until then this PR proves
   the clients are correct and cross-compatible with the sidecar, not that a
   bulk index built through them is.

   The sidecar path was not re-run live after the switch. Its code is untouched
   and its factory selection is covered by tests, but that is a weaker claim
   than having watched it work, and it is stated as the weaker one.

3. **Met.** `make check` green: ruff, eslint, the drift check, mypy strict over
   83 files, 310 passed / 5 skipped, 73 frontend tests. All four modes in § 5.1
   still resolve, and `sidecar` remains the default everywhere.

### PR 3 — `feat/auth-gate` — **done**

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

**Acceptance — met, except the one item that needs eyes.**

48 tests (35 backend, 13 frontend). Then a live container run with the gate on:

| Without a session | |
|---|---|
| `/healthz`, `/api/v1/auth/me`, `/api/v1/auth/logout` | 200 — a login endpoint cannot require a login |
| `/api/v1/repos` (valid body), `/repos/{id}/status`, `/source`, `/neighbors`, `/query` | **401** |
| `/docs`, `/openapi.json` | **404** — F-05 closed |
| Wrong password | 401, no cookie set |

| With a session | |
|---|---|
| Cookie flags | `HttpOnly; Max-Age=43200; Path=/; SameSite=lax` (`Secure` was off only because the probe ran over local HTTP) |
| `/repos/{id}/status` | 200 |
| Gate switched back off | `auth_required:false`, every route open again |

**Not verified: the `/workbench` → `/login` redirect in a real browser.** Its
logic has four unit tests covering unknown / denied / allowed / failure, but
headless screenshots do not work in this environment and that is not a reason to
claim otherwise. **A human should open `/workbench` signed out and confirm it
lands on `/login`, then sign in and confirm it lands back on the workbench.**

One behaviour worth knowing rather than fixing: a request body that is not JSON
at all returns 422 before the gate runs, because Starlette parses the body
before dependencies resolve. A body that is valid JSON with wrong fields returns
401. The disclosure is "this endpoint takes JSON", against an endpoint whose
path the caller already knows, with the OpenAPI schema off.

### PR 4 — `feat/railway-deploy` — **built and locally verified; not deployed**

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

**Acceptance — the code is built and verified locally; the deployment is not
done.** Everything below was observed; the row that needs Railway needs Railway.

| Verified locally | How |
|---|---|
| The nginx template renders correctly under both shapes | Built the image and read `/etc/nginx/conf.d/default.conf` inside it. Defaults gave `listen 80` / `resolver 127.0.0.11` / `http://api:8000`; overriding the three variables gave `listen 8080` / `[fd12::10]` / `api.railway.internal`. **`$api_upstream` and `$request_uri` survived** — `NGINX_ENVSUBST_FILTER` is what stops envsubst eating nginx's own variables, and without it the config would be valid and quietly broken |
| gzip | 760,088 → 269,497 bytes on the built main chunk |
| Cache headers | one `Cache-Control` on hashed assets (the first attempt emitted two), `no-store` on `index.html` |
| SPA fallback and `/healthz` | 200 from the running container |
| `GET /api/v1/repos` | live against the local database: 8 repositories, `truncated: false` |
| Heartbeats and the request budget | 5 tests, including that `close()` still ends a stream while the heartbeat loop runs, and that an overrun emits `TIMEOUT` and **no** `final_answer` |
| The local stack is unchanged | `docker compose up -d --build api` still healthy; `make check` green |

**Not done: no Railway deployment exists.** The runbook is § 10.2, written from
the code rather than from a completed deploy — read it as intended sequence and
correct it against what happens. These are unverified until then: private
networking over IPv6, the platform's request limits against real heartbeats, the
pgvector template, and the first hosted-provider index (§ 6 PR 2).

The combined `agent-worker` container has **not been run**, locally or
otherwise. Its entrypoint is Railway-only and the developer stack does not use
it, so nothing here exercises it.

### PR 5 — `fix/audit-followups` — **done**

Findings that are not launch blockers but should not ship unaddressed.
See the register in § 7 for F-04, F-06, F-07, F-08, F-10, F-14, F-15.

**Acceptance — met.** Eight items, 40 new tests, three commits grouped by what
they are about rather than by which finding they close.

| Finding | What changed |
|---|---|
| F-03 | Request bodies had no size limit anywhere. `query` had a `min_length` and no max, and history was trimmed only *after* parsing |
| F-04 | Both the API and the agent refuse to start on the placeholder key. The length rule applies only when the deployment authenticates its users, which is a proxy for production and is labelled as one |
| F-06 | Resolution checking, credentials refused rather than stripped, and an optional allowlist. **Rebinding stays open** — see below |
| F-07 | Tool cache keyed by `index_revision`, read once per query. No revision means no cache rather than a shared key |
| F-08 | Optional oldest-first cap, off by default. **Deliberately less than "solved"** — see below |
| F-10 | `/readyz`, including the embedding-dimension check § 5.4 asks for |
| F-14 | `--` before the clone URL, and `GIT_TERMINAL_PROMPT=0` |
| F-15 | Timeout, match caps, file-size cap. **The Python fallback is not fully bounded** — see below |

**Three limits this PR does not remove, stated because a closed finding that
quietly leaves the hole open is worse than an open one.**

1. **DNS rebinding is not closed.** Every resolved address is checked, but git
   resolves the name again when it clones, and an answer that changes in between
   defeats the check. The fix is egress filtering at the network — on Railway,
   that is a platform capability this project does not configure.
2. **The workdir cap is a trade, not a cleanup.** The agent reads those trees at
   query time, so evicting a `ready` repository's checkout costs it `read_file`,
   `grep` and `list_directory` until it is re-indexed; search and the call graph
   carry on from Postgres. That is why it is off by default and why the tool's
   error message now says which half stopped working. The durable answer is
   § 11 item 2 — stop reading source from a filesystem.
3. **The `grep` Python fallback can still block.** Python cannot time out a
   single `re` call, so catastrophic backtracking against one long line is
   unbounded. Everything countable is capped. The agent image installs ripgrep,
   so that path runs only where it is absent.

Also unchanged on purpose: the Docker health checks still probe `/healthz`.
`/readyz` is for a load balancer, and wiring it into `depends_on:
condition: service_healthy` would make an unrelated dependency outage block
container startup chains locally.

---

## 7. Findings Register

Every row carries a `file:line` so it can be checked rather than believed.

**Verification column.** `direct` — confirmed in this session by reading the file,
running the command, or resolving the Compose config. `audit` — reported by a
code-audit pass with a citation, not independently re-checked. Treat `audit` rows
as leads to verify when the PR touches them, not as established fact.

| # | Finding | Where | Severity | PR | Verified |
|---|---|---|---|---|---|
| F-01 | ~~No authentication of any kind on `/api/v1/*`~~ **— closed in PR 3.** A shared-account session gate now covers repos, query and inspector; `/internal/*` keeps its own shared-key check. Still one principal, not a tenant model (D-6) | `apps/api/src/dcode_api/main.py` | blocker | 3 | **direct** |
| F-02 | ~~The `api` service in the production Compose file has no embedding or reranker configuration~~ **— fixed in PR 1, and it was wider than this row said: `worker` and `agent` were short too. See § 6 PR 1.** | `docker-compose.prod.yml` | blocker | 1 | **direct** |
| F-03 | ~~No rate limiting, no request-size limit, no quota~~ **— closed across PR 3 and PR 5.** Anonymous access gone, per-session daily cap, and bounds on the URL, the query, each turn and the turn count | `packages/shared/src/dcode_shared/schemas.py` | blocker | 3, 5 | **direct** |
| F-04 | ~~`INTERNAL_API_KEY` defaults to a published literal with no startup guard outside Compose~~ **— fixed in PR 5.** API and agent both refuse to boot on it | `packages/shared/src/dcode_shared/internal.py` | high | 5 | **direct** |
| F-05 | ~~`/docs`, `/redoc` and `/openapi.json` are publicly served~~ **— closed in PR 3**, off in production and pinned by a test; observed 404 on a gated container | `apps/api/src/dcode_api/main.py` | high | 3 | **direct** |
| F-06 | **Mostly fixed in PR 5**: resolution checked, credentials refused, optional allowlist added. **Rebinding remains open** — git re-resolves at clone time and that needs network egress filtering | `apps/api/src/dcode_api/routes/repos.py` | high | 5 | **direct** |
| F-07 | ~~The agent tool cache key omits `index_revision`~~ **— fixed in PR 5**, keyword-only with no default so a new call site cannot reintroduce it | `packages/shared/src/dcode_shared/cache.py` | high | 5 | **direct** |
| F-08 | **Partly addressed in PR 5**: an optional oldest-first cap, **off by default**, because eviction costs an evicted repository its file tools until re-index. The durable fix is § 11 item 2 | `apps/worker/src/dcode_worker/stages/prune.py` | high | 5 | **direct** |
| F-09 | ~~No repository list endpoint~~ **— fixed in PR 4.** `GET /api/v1/repos`, merged behind the localStorage recents so a reader on a new device sees what is indexed. Verified live against the local database: 8 repositories returned | `apps/api/src/dcode_api/routes/repos.py` | high | 4 | **direct** |
| F-10 | ~~No readiness probe~~ **— fixed in PR 5.** `/readyz` covers database, Redis and the embedding-dimension agreement; `/healthz` stays shallow on purpose | `apps/api/src/dcode_api/readiness.py` | medium | 5 | **direct** |
| F-11 | ~~The two documented production Compose invocations disagree; one of them republishes Postgres, Redis and the RabbitMQ UI~~ **— fixed in PR 1.** | `README.md`, `.env.production.example` | medium | 1 | **direct** |
| F-12 | ~~`RERANKER_ENDPOINT` defaults to a dead loopback address in the production template~~ **— fixed in PR 1, pinned by a test.** | `docker-compose.prod.yml`, `.env.production.example` | medium | 1 | **direct** |
| F-13 | Embedding retries are 12 attempts against a 300 s timeout; with `prefetch_count=1` one bad batch stalls the entire indexing queue. **Knob added in PR 1 (`EMBEDDING_TIMEOUT_SECONDS`); the values are set in PR 2, where the path that needs them exists.** | `packages/shared/src/dcode_shared/embedding.py:19-20` | medium | 1 → 2 | audit |
| F-14 | ~~`git clone` receives the URL with no `--` separator~~ **— fixed in PR 5**, plus `GIT_TERMINAL_PROMPT=0` | `apps/worker/src/dcode_worker/stages/clone.py` | medium | 5 | **direct** |
| F-15 | **Mostly fixed in PR 5**: timeout, match caps, file-size cap. **A single pathological `re` call in the fallback is still unbounded** — Python offers no way to interrupt one | `apps/agent/src/dcode_agent/tools/grep.py` | medium | 5 | **direct** |
| F-16 | ~~nginx serves the bundle uncompressed~~ **— fixed in PR 4**, measured on the built image at 760,088 → 269,497 bytes. Also fixed a duplicate `Cache-Control` header the first attempt introduced | `apps/frontend/nginx.conf.template` | low | 4 | **direct** |
| F-17 | ~~No `.dockerignore` anywhere~~ **— fixed in PR 4**, one at the root and one for `apps/frontend` | repository root | low | 4 | **direct** |
| F-21 | ~~A copy-pasteable setup block in § 10.1 contained placeholders, was pasted verbatim, and the placeholder became the credential — the API then refused to boot~~ **— fixed in PR 4** by rewriting the block to substitute its own values. The refusal was correct; the instructions were the defect | `Deploy.md` §10.1 | low | 4 | **direct** |
| F-19 | ~~A `$` in an env-file value is silently eaten by Compose interpolation, so a `$`-separated password hash reached the container as 22 of ~100 characters and every login failed while the service reported healthy~~ **— fixed in PR 3** (format changed, and the hash is now parsed at startup). Applies to any hand-picked secret containing `$` — see § 2.3 | `apps/api/src/dcode_api/auth.py` | high | 3 | **direct** |
| F-20 | ~~The test suite reads the developer's `.env`, so `make check` is not hermetic — enabling the gate locally failed four unrelated tests with no hint of the cause~~ **— fixed in PR 3** by a root `conftest.py` pinning the settings whose defaults tests assert | `conftest.py` | medium | 3 | **direct** |
| F-18 | Model sidecars download weights from Hugging Face at runtime with no cache volume | `infra/docker/embedding.Dockerfile`, `infra/docker/reranker.Dockerfile` | low | — | **direct** |

F-18 is recorded but **not scheduled**: D-1 removes the sidecars from the
deployment path, so it only affects local Docker-profile use. It is left as a
known cost of that mode rather than fixed speculatively.

### 2.3 A `$` in an env-file value is eaten before the container sees it

Found while verifying PR 3, and it had already produced a working-looking
failure. Docker Compose interpolates `${VAR}` **and bare `$VAR`** inside
env-file values. A PBKDF2 hash of the conventional
`pbkdf2_sha256$600000$salt$hash` form therefore reached the container as 22
characters with three of its four segments gone.

Nothing errored. Compose printed interpolation warnings among its normal
output, the API booted, the health check passed, and **every login failed
forever** — indistinguishable from a wrong password.

Two changes, because either alone leaves the trap open:

- the hash format joins its segments with `.` instead of `$`, so the character
  never appears in the value (base64url contains no `.`, so it stays
  unambiguous). Escaping as `$$` would also work and would be remembered by
  nobody;
- `auth_configuration_error()` now parses the hash rather than checking it is
  non-empty, so a value corrupted by any means stops the boot instead of
  producing a service that is up and unopenable.

**This applies to every secret, not just this one.** A Postgres or RabbitMQ
password containing `$` will be corrupted the same way. `secrets.token_urlsafe`
output is safe (`A-Za-z0-9_-`); anything hand-picked is not.

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

### 10.1 Seeing the auth gate locally

The two checks above that need a human need the gate switched on first, and
nothing switches it on by default. This is how, written down because otherwise
the next person rediscovers it.

**The login page itself needs none of this.** `/login` is a public route and
renders whatever the gate is doing: `http://localhost:5173/login`. What that
does *not* show you is the behaviour — the redirect, the refusal, the error —
which is the part worth looking at.

**One command, and it does the substitution itself.** An earlier version of
this section was a `cat >> .env` block with `<paste from step 1>` inside it.
It got pasted verbatim, the placeholder became the value, and the API refused
to boot — correctly, and with the right message, but the walkthrough should not
be the thing that breaks the stack. A copy-pasteable block containing
placeholders is a trap; this one has none.

```bash
# Prompts for the password (unechoed), generates the secret, appends nothing
# you have to edit afterwards. Run from the repository root.
python3 - <<'SETUP'
import getpass, pathlib, secrets, subprocess, sys
password = getpass.getpass("Gate password: ")
if not password or password != getpass.getpass("Confirm:        "):
    sys.exit("passwords empty or do not match")
digest = subprocess.run(
    [sys.executable, "-c",
     "import sys; sys.path[:0]=['apps/api/src','packages/shared/src'];"
     "from dcode_api.auth import hash_password; print(hash_password(sys.argv[1]))",
     password],
    capture_output=True, text=True, check=True,
).stdout.strip()
pathlib.Path(".env").open("a").write(
    "\n# --- local auth-gate check; delete this block afterwards ---\n"
    "AUTH_ENABLED=true\n"
    "AUTH_USERNAME=reviewer\n"
    f"AUTH_PASSWORD_HASH={digest}\n"
    f"AUTH_SESSION_SECRET={secrets.token_urlsafe(48)}\n"
)
print("appended to .env")
SETUP

# Recreate the API. No --build: the image already carries the code and only
# the environment changed.
docker compose up -d api
```

If the API exits on boot with `AUTH_PASSWORD_HASH is not a valid hash`, the
value in `.env` is not one — the fail-closed check in § 6 PR 3 doing its job.
Fix the line rather than the check.

The Vite dev server does not need restarting. There is no build-time switch —
the SPA asks `/api/v1/auth/me` at runtime and renders accordingly.

**Then look at four things in a real browser:**

| Do this | Expect |
|---|---|
| Open `/workbench` signed out | a brief `checking session…`, then a redirect to `/login` |
| Submit a wrong password | `Incorrect username or password.` under the form, no navigation |
| Submit the right password | lands on `/workbench`, workbench works |
| Open `/` and `/methodology` | load normally, **no** sign-in |

Rows one and three are the items § 10 records as unverified.

**Why the cookie works here at all**, since it is the question that decides
whether any of this can be tested locally: `apps/frontend` has no `.env`, so
`VITE_API_BASE_URL` is undefined and `BASE_URL` is the empty string
(`src/api/client.ts`). The SPA therefore calls **same-origin** `/api/v1/*` on
port 5173 and `vite.config.ts` proxies `/api` to the gateway. No cross-origin
request, so `allow_credentials=False` on the CORS middleware never comes into
it. Point `VITE_API_BASE_URL` at `http://localhost:8000` and that stops being
true — the browser would refuse to send the cookie and the CORS policy would
refuse the credentialed request.

**Three things that will otherwise waste your time:**

- `AUTH_COOKIE_SECURE` defaults to true, and browsers treat `http://localhost`
  as a trustworthy origin, so it should hold. If a successful sign-in bounces
  straight back to `/login`, the cookie is not being stored — set
  `AUTH_COOKIE_SECURE=false` and recreate the API.
- **Do not hand-edit the hash back to `$` separators.** That is § 2.3, and its
  symptom is a login that fails forever with nothing in the logs.
- `make check` is unaffected. The root `conftest.py` pins `AUTH_ENABLED=false`
  for tests, which exists precisely because a locally-enabled gate once failed
  four unrelated tests with no hint of why (F-20).

**Afterwards**, delete the block from `.env` and `docker compose up -d api`.
`curl -s localhost:8000/api/v1/auth/me` returning `"auth_required":false`
confirms you are back.

---

### 10.2 Railway runbook

Written from the code, not from a completed deployment — **nothing has been
deployed yet** (§ 6 PR 4). Treat it as the intended sequence, and correct it
against what actually happens.

**The configuration is committed.** `infra/railway/{api,agent-worker,frontend}.toml`
carry the build and deploy settings, and
[`infra/railway/README.md`](infra/railway/README.md) is the variable sheet —
which service needs what, and the two rules that fail silently. What follows is
the part that cannot live in a file.

**Services.** Six. Only `frontend` gets a public domain.

| Service | Image | Notes |
|---|---|---|
| `frontend` | `infra/docker/frontend.Dockerfile` | Public. Set `API_UPSTREAM` and `DNS_RESOLVER`; `PORT` is injected. Builds from the repository root — it used to build from `apps/frontend`, changed so no service needs a Root Directory. |
| `api` | `infra/docker/api.Dockerfile`, context repo root | Private. Set `HOST=::` — Railway's private network is IPv6 and a service bound to `0.0.0.0` is reachable by nothing there. |
| `agent-worker` | `infra/docker/railway-agent-worker.Dockerfile`, context repo root | Private. **Owns the only volume**, mounted at `WORKDIR_BASE`. Set `HOST=::`. |
| Postgres | Railway **pgvector** template | Not the plain Postgres template — R-3. |
| Redis | Railway template | |
| RabbitMQ | Railway template | |

**Order.** Postgres/Redis/RabbitMQ first, then `api`, then `agent-worker`, then
`frontend`.

The migration is **not** a manual step: `api.toml` runs it as a
`preDeployCommand`, in that container, before the deployment takes traffic. That
is where it belongs rather than where it is convenient — the migration reads
`EMBEDDING_DIM` to size the pgvector column, and that variable lives on the
`api` service (§ 6 PR 1). Running it anywhere else is how the column ends up at
a dimension nothing agrees with. `upgrade head` is idempotent, so every deploy
running it is fine.

The consequence: **`EMBEDDING_DIM` must be correct before the first deploy of
`api`**, not before some later step. Afterwards the column is fixed and changing
it means a new volume.

**Variables that must agree across `api`, `agent-worker` and each other**:
`EMBEDDING_*`, `RERANKER_*`, `INTERNAL_API_KEY`, `EMBEDDING_DIM`. § 5.4 explains
what a mismatch looks like, which is nothing — no error, just worse retrieval.

**Values with a `$` in them will be corrupted** if they pass through an env
file (§ 2.3). Railway's dashboard is not an env file, so pasting there is safe;
a `railway.json` or a bulk import is not.

**Set on `api`:** `AUTH_ENABLED=true`, `AUTH_USERNAME`, `AUTH_PASSWORD_HASH`,
`AUTH_SESSION_SECRET`, `AUTH_COOKIE_SECURE=true`, `DOCS_ENABLED=false`.
Railway serves HTTPS, so the Secure cookie is correct there.

**Health checks.** Point Railway's at `/readyz`, not `/healthz`. The shallow one
reports ok with every dependency down; the deep one covers the database, Redis
and the embedding-dimension agreement, and returns 503 with a per-check reason.
It skips the dimension check when `chunks` does not exist yet, so it is safe to
have configured before the migration step above.

**Then walk § 10's checklist.** The rows that need a browser need a browser.

**Three things to decide here rather than discover.** The first index runs
through the hosted embedding API for real — roughly 23 requests for
`psf/requests` — and that path has never been exercised (§ 6 PR 2). Set
`WORKDIR_MAX_REPOS` to something the volume can hold, since it defaults to
never evicting and read § 6 PR 5 for what eviction costs. And consider
`REPO_URL_ALLOWED_HOSTS`: on a gated demo the login wall is the real control,
but it is the only rule in the URL check that states what is *allowed*, and DNS
rebinding is not closed without it or network egress filtering.

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
