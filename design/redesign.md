# Claude Code brief (v2) — adopt the workbench + landing redesign

> Supersedes v1. Updated after a full read of the codebase: the real architecture is folded in below so you don't re-explore from scratch, the code-inspector endpoints are now concrete, and the thread is a **real multi-turn conversation** (backend changes required).

## Context

**Dcode** is a structure-aware code-retrieval platform. A React SPA talks to a single FastAPI **gateway** (`apps/api`), which proxies to a LangGraph **agent** (`apps/agent`) over an internal SSE endpoint; a **worker** does indexing (clone → parse → embed → graph) into Postgres + pgvector + Redis, driven by RabbitMQ. The SPA never touches the agent, DB, or queue directly — everything goes through `/api/v1/*`.

The current frontend (`apps/frontend`) is organized around the backend's API shape: three routes — `/` (Index), `/query` (Query), `/compare` (Compare). **That IA is being replaced.** Two design prototypes at repo root define the new direction:

- **`design/dcode-workbench.html`** — the redesigned **product**: a single continuous exploration workbench (three panes: topbar repo switcher; center conversational thread + composer; right-hand live code + call-graph inspector). Collapses Index/Query/Compare into one experience.
- **`design/dcode-landing.html`** — a marketing / demo landing page (also usable as a live demo in place of slides).

These `design/*.html` files are **static design sources, not the running app.** Confirm their exact filenames/paths.

## The one rule that governs everything

- The **prototypes are the source of truth for visual design, IA, and interactions.** Reproduce their look and behavior faithfully.
- The **backend is the source of truth for data and contracts.** Verify every payload against the real server code (`packages/shared` schemas/events, `apps/api`, `apps/agent`), never the prototype's mocked data.
- **Reimplement** the prototypes as idiomatic React + Tailwind components. Do **not** paste raw HTML. Do **not** invent a new visual direction or "improve" the aesthetic — it was chosen deliberately (see tokens).

## Non-negotiables

1. **Never fabricate data or fake success.** The prototypes mock the SSE stream, groundedness, source, and graph edges. The real UI must be driven by real endpoints. `verified` is trustworthy — the agent's `groundedness_check` re-validates every citation against the symbol table and redacts unverified ones — so render `verified: false` honestly (distinct, not green-checked). If an endpoint doesn't exist, add a thin real one; never stub the UI with fake "verified" data.
2. **Match the stack and conventions.** React 18 + TS strict + Vite + Tailwind + React Router v6 + TanStack Query v5 (front end ~2k lines, keep it light). Backend is FastAPI with shared Pydantic schemas in `packages/shared`. Reuse existing patterns before adding new ones.
3. **Small, reviewable changes.** Scoped commits. Run `make check` and `make frontend-build` (plus typecheck/lint) and fix what you touch.
4. **Confirm the two open questions below before implementing the parts that depend on them.**

## Design tokens to preserve exactly

Lift these from the prototype `:root` into the real project (`tailwind.config` theme `extend` and/or a CSS-vars layer). This palette is intentional — it avoids the generic "cream + terracotta serif" AI-default look. Keep the identity.

- **Surfaces (cool pale paper, NOT warm cream):** `--paper:#EEEDF2`, `--surface:#FBFBFD`, `--sunk:#E7E6EE`
- **Ink (near-black, faint violet undertone):** `--ink:#1B1826`, `--ink-2:#575369`, `--ink-3:#8B8799`
- **Hairlines:** `--line:#DDDBE6`, `--line-2:#CBC8D8`
- **Brand (deep indigo):** `--brand:#3A2FA0`, `--brand-hover:#2C2380`, `--brand-wash:#E7E4F7`
- **Status (clear of the brand hue):** good/verified `--good:#1F7A46` (`#DEEFE3`); failed `--bad:#C23A2B`; pending/indexing `--warn:#9A6A15` (`#F0E6D0`)
- **Type — three load-bearing roles:** display/prose answers → **Newsreader** (serif, the "human understanding" voice); body/UI → **IBM Plex Sans**; data/code/`file:line`/IDs/metrics → **IBM Plex Mono** (the "machine-verified evidence" voice). Prefer self-hosting (`@fontsource`) over CDN for the nginx static build; `display: swap` + fallbacks (`Georgia` / `system-ui` / `ui-monospace`).
- **Signature to keep:** the **verified stamp** on citations, the **serif↔mono two-voice** split, and the differentiator moment — **click a citation → the right pane shows real source + call-graph neighbors, themselves clickable to walk the graph.** This is the product's centerpiece.

## What's already established (don't re-explore — build on it)

- **Single seam:** all frontend↔backend logic lives in `apps/frontend/src/api/client.ts` (three functions: `submitRepo`, `getRepoStatus`, `streamQuery`) and `apps/frontend/src/api/types.ts` (a hand-mirrored copy of `dcode_shared` schemas). `BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''` → relative `/api/v1/*` (dev: Vite proxy → :8000; prod: nginx → `api:8000`). To change any API you touch these two files.
- **Flow A — indexing (REST + polling):** `POST /api/v1/repos {url}` → 202 `{repo_id, status:queued}`; `GET /api/v1/repos/{id}/status` polled by TanStack Query `refetchInterval` (1500ms) until `ready`/`failed`. Status = Postgres row (durable) merged with Redis (per-stage progress): `{status, progress, stages, error, warnings}`.
- **Flow B — query (SSE):** `streamQuery` is a hand-written SSE parser over `fetch` + `getReader()` (POST with JSON body, so not `EventSource`; splits on `\n\n`, handles cross-chunk buffering). The gateway `StreamingResponse` proxies the agent stream chunk-by-chunk and buffers it to cache in Redis (`query:{repo_id}:{hash(query)}`) only when the stream had no `error`.
- **SSE events + real timing:** `thought`, `tool_call`, `tool_result` stream first (possibly multi-hop); then `partial_answer` deltas (token stream); then — **after the graph completes** — `citation × M` and `final_answer` arrive together (citations are flushed at the end, not mid-run). `error` can arrive as a graceful fallback if the agent is unreachable. The frontend merges citations by `symbol | file_path | line` and hides `partial_answer` from the event log.
- **Inspector data is in Postgres, reachable from the gateway** (the gateway already reads Postgres for status): AST chunks live in `chunks` (`content`, `symbol_name`, `file_path`, `start_line`, `end_line`, `chunk_type`); the call graph lives in `symbols` + `edges` (`edge_type` ∈ calls/imports/inherits/references; reverse-lookup indexes on `target_id` exist). So the inspector endpoints can be **thin read-only Postgres queries in `apps/api`, no agent involvement.**
- **Known drift:** `types.ts` `RepoStatusResponse` is missing the backend's `url` field (harmless today). Contract is hand-synced; the README plans openapi-typescript for M2.

## Two open questions — confirm first, then implement

1. **Source fallback:** if a cited `file:line` doesn't fall inside any AST `chunk` (e.g., a line outside indexed function/class/module boundaries), `chunks.content` won't have it. Determine whether the worker retains the git clone on disk (then read the file directly as a fallback) or not (then the inspector shows a graceful "source not indexed at this granularity" state). Do **not** 500.
2. **Conversation threading in the planner:** decide how history enters the agent — the standard pattern is a light **contextualization / query-rewrite** step (rewrite the follow-up into a standalone query using prior turns) feeding retrieval + planning, while the **groundedness guardrail stays unchanged** (history informs planning/retrieval only; citations are still verified against the index — never let history introduce unverifiable citations). Confirm the cleanest insertion point in `apps/agent` graph/planner.

---

## Phase 1 — Design system extraction

Port the tokens into `tailwind.config` / a CSS-vars layer; wire the three fonts (self-hosted). Build shared primitives used by **both** landing and workbench, in one place: `Button` (primary/ghost), `StatusPill` (ready/indexing/failed), `VerifiedMark`, mono `CodeChip`, `CitationChip`. Keep the cool-paper + indigo + Newsreader/Plex identity precisely.

## Phase 2 — The workbench (main work)

Replace the `/` `/query` `/compare` tab IA with the single workbench from `design/dcode-workbench.html`.

**Shell & layout.** Three panes; responsive drawers exactly as in the prototype (inspector → right drawer under ~1180px; history rail → left drawer under ~760px; scrim).

**Repo switcher (replaces Index).** Dropdown backed by the real repo list + `GET status`, with the `indexing…` progress state. "Index a new repository" calls `POST /repos` and shows progress **in place** (no separate page). Selecting a repo scopes thread + inspector to that `repo_id`. (Recent repos already persist in `localStorage`; reuse.)

**Thread driven by the real `/query` SSE stream.** Map events precisely:
- `thought` / `tool_call` / `tool_result` → the collapsible per-answer **trace** (a compact "grounded 1.00 · N tools" pill expanding to a timeline; collapsed by default).
- `partial_answer` → stream deltas into the serif answer (typewriter).
- `citation` (verified true/false) → inline citation chips + verified state, honestly.
- `final_answer` → close the turn, show groundedness, and **render the answer markdown properly** (the old UI printed literal `**bold**` — render markdown → sanitized React, never raw text; keep `code`, lists, emphasis).
- `error` → an error state in the interface's voice.
- **Animation must match real timing:** stream thought/tool events, then citations + final arrive together at the end. Do **not** fake token-level "verifying → verified" stamping mid-run; reflect the end-of-run arrival. (Keep the existing merge-by-`symbol|file_path|line` logic and its reserved support for future mid-run citations.)

**Inline citations ↔ inspector.** Turn `file:line` references in the answer into clickable `CitationChip`s associated with their `citation` events (carry `symbol`/`file_path`/`line`, and a chunk/symbol id if available). Clicking opens the inspector on that source and marks the chip active.

**Conversation history — real multi-turn (backend + frontend).** The thread is a genuine conversation; follow-ups resolve relative references ("who calls *it*?"). Implement server-side statelessly — the client sends prior turns each request (matches the existing stateless design; no server session store):
- **Schema (`packages/shared` + `apps/api`):** add an optional `history` field to the `/api/v1/query` request — a bounded list of prior turns (`{role, content}` or `{question, answer}`; cap turns / token budget). Mirror into `types.ts`.
- **Gateway (`apps/api` query proxy):** pass `history` through to the agent `/internal/query` body.
- **⚠️ Cache-key fix (correctness trap):** the Redis key is `query:{repo_id}:{hash(query)}`. With history, the same query string means different things in different contexts — the key **must** incorporate the history (`hash(history + query)`), or skip cache when `history` is non-empty. Otherwise a context-dependent follow-up will hit a stale single-turn answer. Fix this.
- **Agent (`apps/agent`):** `/internal/query` accepts `history`; the planner uses it per open question #2 (contextualize/rewrite → retrieve/plan), **groundedness guardrail unchanged**.
- **Frontend:** the composer appends a new turn to the same thread and sends the prior turns (user questions + assistant final answers, trimmed to the cap) as `history` via `streamQuery`. History accumulates in the left rail.

**Code + call-graph inspector (the signature).** On citation click:
- Fetch and render **real source** at that `file:line` with proper syntax highlighting (Shiki / Prism / highlight.js — replace the prototype's throwaway highlighter). Highlight the cited line.
- Render **call-graph neighbors** — *Called by* / *Calls* / *References* — each row clickable to navigate to that symbol's source (chaining exploration through the graph).
- **New thin read endpoints in `apps/api` (Postgres-only, scoped by `repo_id`):**
    - Source — e.g. `GET /api/v1/repos/{id}/source?symbol=…&file_path=…&line=…` → locate the `chunks` row (by symbol+file, or the chunk whose `[start_line, end_line]` contains `line`) and return `content` + line range + symbol metadata; apply the fallback from open question #1.
    - Graph — e.g. `GET /api/v1/repos/{id}/symbols/{symbol}/neighbors` → look up `symbols`, then `edges` outgoing (calls/imports/inherits/references) and incoming (reverse for *called-by*), returning neighbors with `file:line` so they're clickable.
    - Reuse the agent's existing graph-query logic if it's already factored into a shared module; otherwise keep these as straightforward read queries. Read-only, minimal, tenant-scoped.

## Phase 3 — Landing route + methodology

- Implement `design/dcode-landing.html` as a separate route (e.g. `/`), reusing the shared primitives + tokens. Preserve the hero "reasoning → verified stamp" proof animation and scroll reveals; **respect `prefers-reduced-motion`**. CTAs route into the workbench.
- **Move the evaluation / H1 story out of the product** into a `/methodology` page (or landing section): the falsifiable hypothesis, the B0–B4 baseline ladder, the honest current result. `ComparePage` is already a static snapshot (`demo/evalSnapshot.ts`, no backend) — migrate that content here; read numbers from the snapshot, don't invent metrics. Copy stays honest and consistent with the README.

## Phase 4 — Retire the old IA

Remove/redirect `/`, `/query`, `/compare` tabs into the new structure. The old `ComparePage` is superseded by `/methodology`. Delete now-dead pages/components; no orphans.

## Contract sync (do this alongside, not last)

New query fields + two new inspector endpoints widen the hand-synced contract, and `types.ts` has already drifted (`url`). Adopt **openapi-typescript** (auto-generate TS from the gateway's OpenAPI) as the README's M2 plan intends — or, at minimum, fix the `url` drift and mirror every new field carefully. Prefer the generator.

## Quality bar

Responsive to mobile; visible keyboard focus; `prefers-reduced-motion` honored; TS strict passes; `make check` + `make frontend-build` green; no fabricated data (verified means verified); the result visibly matches the prototypes.

## What to report back

Answers to the two open questions; what changed (files/components/routes); the exact new backend endpoints + query-schema/history changes and why; the cache-key change; any gap you couldn't close and what's needed; and how to run the app to see it (screenshots if you can).