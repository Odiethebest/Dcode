# Dcode Final Report

## Summary

Dcode is a structure-aware code understanding stack built around four runtime surfaces:

- async indexing (`POST /api/v1/repos` → worker pipeline)
- internal retrieval / graph APIs
- SSE-based agent answers with grounded citations
- an evaluation harness and comparison UI

As of **2026-07-29**, the repository delivers a complete local vertical slice:

- a real indexing pipeline for Python repositories
- retrieval and graph lookup endpoints
- self-hosted embedding and reranker sidecars, exercised on a full real-model run
- a working agent loop with 10 tools
- a single exploration workbench whose citations open real indexed source and
  walk the call graph, plus a `/methodology` page reporting this evaluation
- a production-shaped Docker Compose package with static frontend serving

**Read this report for the verdict.** H1 is recorded **unsupported** on the
real-model run; the evaluation section below gives the numbers, why the call
graph's contribution is unmeasured rather than absent, and what would re-open the
question. The claim this project cares about most is not that H1 passed — it is
that the answer is honest and checkable.

## Implemented System

### Indexing

- `git clone --depth=1`
- Python `ast` parse
- AST-boundary chunking for module docstrings, functions, classes, and methods
- chunk persistence with embedding cache
- optional real code embedding through the embedding sidecar
- graph rebuild with symbol definitions, module-level import edges, and best-effort intra-repo call edges

### Retrieval and Agent

- `/internal/search`
- sparse retrieval, dense retrieval hook, RRF fusion, and optional reranking
- `/internal/find_definition`
- `/internal/find_references`
- `/internal/get_call_neighbors`
- `/internal/get_dependencies`
- `/internal/get_dependents`
- `/internal/get_file_outline`
- agent SSE events: `thought`, `tool_call`, `tool_result`, `citation`, `partial_answer`, `final_answer`, `error`
- groundedness verification against `chunks` and `symbols`

### Frontend and Deployment

- `/workbench` — one continuous exploration surface: topbar repo switcher, a
  conversational thread driven by the live SSE stream, and a right-hand code +
  call-graph inspector. Clicking a citation opens the real indexed source with
  the cited line marked; call-graph neighbours are themselves clickable, so you
  can walk the graph from any answer. Replaced the earlier one-tab-per-endpoint
  IA (`Index` / `Query` / `Compare`), retired in Phase 4.
- `/` — marketing landing; `/methodology` — the evaluation story for reviewers,
  reading the same generated snapshot as this document; `/preview` — design-system
  gallery.
- nginx-hosted static frontend image
- `docker-compose.prod.yml` with frontend-only public exposure and `/api/*` proxying

## Evaluation Snapshot

The recorded suite uses 16 manually curated `requests` questions, measured on a
full real-model run. Every figure in this section is generated from the results
directory by `scripts/sync_eval_artifacts.py` and is not transcribed by hand;
`make check` fails if the two diverge.

Aggregate metrics:

<!-- BEGIN generated: eval-suite-metrics -->

| Baseline | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` legacy lexical heuristic | 0.214 | 0.221 | 0.204 | 1.000 |
| `B2` Dense RAG | 0.474 | 0.325 | 0.333 | 1.000 |
| `B3` Hybrid + rerank | 0.542 | 0.596 | 0.508 | 1.000 |
| `B4` Dcode (hybrid + call graph + agent) | 0.542 | 0.596 | 0.508 | **0.916** ⚠️ below the 0.95 guardrail |

Source: `results/eval-real/` · verdict written 2026-07-28 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · synthesis gpt-4o-mini

The date is **recovered, not recorded** — the harness writes no timestamp. How it was reconstructed, and what it does not establish, is in `results/eval-real/provenance.json`.

<!-- END generated: eval-suite-metrics -->

H1 verdict:

<!-- BEGIN generated: eval-h1-verdict -->

**Decision: `unsupported`**

H1 is supported only if B4 beats **both** B2 and B3 by at least `0.050` composite points on **both** L2 and L3.

| Level | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | Cleared |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` cross-file | 8 | 0.448 | 0.586 | 0.562 | +0.113 | −0.024 | no |
| `L3` architecture | 3 | 0.315 | 0.371 | 0.324 | +0.009 | −0.047 | no |

<!-- END generated: eval-h1-verdict -->

Recall by question level — the ladder that did hold up:

<!-- BEGIN generated: eval-level-ladder -->

| Level | n | `B1` Recall@5 | `B2` Recall@5 | `B3` Recall@5 | `B4` Recall@5 |
|---|---:|---:|---:|---:|---:|
| `L1` single-hop | 5 | 0.200 | 1.000 | 1.000 | 1.000 |
| `L2` cross-file | 8 | 0.208 | 0.292 | 0.396 | 0.396 |
| `L3` architecture | 3 | 0.250 | 0.083 | 0.167 | 0.167 |

<!-- END generated: eval-level-ladder -->

### Reading the result honestly

**H1 is unsupported.** B4 clears the +0.05 bar against dense RAG on cross-file
questions and against nothing else. The threshold, the question set, and the
metric definitions were fixed before the run and have not been touched since.

**The verdict survives run-to-run noise, which it had never been tested against.**
Answer synthesis is stochastic, and every figure above comes from a single run. Six
further B4 runs — three on this exact synthesis code, three with a changed citation
prompt, all in one session against this index — bound what a repeat costs. Recall@5,
MRR and nDCG@5 came back byte-identical in all six, and B3's groundedness is 1.000 on
every question, so the entire margin distribution comes from B4's synthesis and works
out to exactly a quarter of its level's groundedness spread. Measured that way, the
distance from the +0.05 bar is **at least 6.9 standard deviations at the least
favourable of the four arm-and-level combinations, and 21.6 at the most.** Nothing in
synthesis variability reaches that, so `unsupported` is not an artefact of having
measured once. Design, criteria fixed before the numbers were seen, and every per-run
figure: [`results/b4-citation-fix-experiment.md`](../../results/b4-citation-fix-experiment.md).
Those runs are outside `results/eval-real/`, so the two ratios quoted here are the one
place in this document carrying a figure the artifact drift check does not cover — that
file is their authority.

**The archived ladder is not a BM25 validation.** It shows a monotonic
legacy-lexical → dense → hybrid+rerank ordering on the single-hop and cross-file
levels, but its B1 was the old `ILIKE` plus fixed substring bonuses rather than
BM25. Because B3 and B4 used that same sparse component, the corrected BM25 path
must be run across B1–B4 before making the stronger hybrid-ablation claim.

**B4's groundedness sits below the 0.95 guardrail.** This is the one number in
this report that an earlier version stated too favourably — it was written as
`0.95` and described as "at the threshold floor", when the real value is under
the bar. The agent sometimes emits a citation that fails verification.
Unverifiable references are stripped from the delivered answer, so what a user
reads stays verified; the *score* deliberately counts the draft **before**
redaction, so a heavily-redacted answer still scores low. That is the honest
measure of how clean the draft was, and the dip is a real failure against a
pre-registered guardrail.

One qualification on that number, not on the finding. Four runs of this same synthesis
code — the archived suite run plus three repeats — all came in under the bar, and the
recorded figure is the **highest** of the four; their mean sits further below the
guardrail than the value this report displays. The direction is therefore solid, and if
anything understated. The magnitude is not: the shortfall the recorded figure implies is
about the same size as the spread between repeats. **No sentence here quantifies how far
under the bar the system sits**, because one 16-question run cannot support it. Note the
narrowness of that retraction: *this run came in at the recorded figure* stays exactly
true and is what the generated blocks and the UI state. What is withdrawn is reading
that figure as where the system sits, which is a different claim and the one a reader
takes away.

**L3 is statistically fragile.** With n=3, one question moves the average and
significance is not computable. Sparse `B1` posts the *highest* L3 recall of any
rung, which on three questions is almost certainly one lucky lexical hit rather
than evidence that the legacy heuristic understands architecture. L3 should not be read in
either direction. Expanding it is a precondition of the next run.

### Why B4 cannot currently beat B3

**B4's scored retrieval is identical to B3's by construction.** The `retrieve()`
call the harness measures is the same hybrid search in both rungs — which is why
every retrieval cell in those two rows matches to the digit. The call-graph
tools fire later, *inside the agent's answer*, and the harness scores retrieval,
not the answer. The differentiator is therefore invisible to Recall, MRR and
nDCG, leaving groundedness as the only channel where B4 can differ from B3 — and
B4's groundedness dipped.

Under this scoring **B4 cannot beat B3 no matter how well the graph works.**

The precise claim is that the graph's contribution is **unmeasured**. Not
"invisible", not "unvalidated", not "it did not work" — the harness never looked
at the output the graph contributes to. Claiming either more or less than that
would be inaccurate.

## What Worked

- The repo now has a defensible vertical slice rather than disconnected stubs.
- Real embedding and reranker clients are implemented behind environment-driven sidecar boundaries.
- Graph coverage has moved beyond module imports with best-effort intra-repo call edges.
- `repo_id` isolation, caches, and internal-route protection are enforced in code and tests.
- The production packaging path is now explicit and locally smoke-tested.
- Citation verification demonstrably does work: it catches unverifiable
  references and strips them from delivered answers. That is also *why* B4's
  groundedness reads below the guardrail — the score counts the draft before
  redaction, so the guardrail failing is the mechanism reporting itself
  honestly rather than the mechanism being absent.
- Every number a user or reviewer sees is generated from the results directory.
  The UI, this report, and the README cannot disagree without `make check`
  failing.

## Iteration History

The previous version of this report set re-open criteria and they were met, so
they are recorded here rather than deleted — the point of a pre-registered bar is
that you can see what happened when it was tested.

**Criteria set 1 (met).** Re-index with real code embeddings and a matching
`EMBEDDING_DIM`; enable and record the reranker; re-run B1–B4 on the same suite.

**What that run showed.** The stub-model snapshot had made B2, B3 and B4
numerically identical (stub dense retrieval returned nothing, so all three
degenerated to the same sparse path). With real models the baselines separated
and the hybrid ladder appeared — a genuine result the stub run had concealed. H1
still came out unsupported, but for a completely different and much more
informative reason.

**The new limitation it exposed.** With the baselines finally distinct, it became
visible that B4's *scored* retrieval is the same call as B3's, so the call graph —
the entire hypothesis — is never scored. The first run could not have revealed
this, because B3 and B4 were identical for an unrelated reason. Meeting the first
set of criteria is what made the real obstacle legible.

## H1 Decision

**H1 remains unsupported** on the full real-model run — see the generated verdict
table above for the margins, read straight from `h1_report.json`.

The decision is no longer scoped to a muted baseline. Real embeddings and a real
reranker were used, the baselines separated as they should, and B4 still did not
clear the bar. What changed is the *reason*: the obstacle is now a diagnosed gap
in what the harness measures, not an artefact of stub models.

### Criteria set 2 — to re-open H1

Approved, not yet implemented. Numbered so a later run can be checked against them.

1. **Score B4 on its final evidence set.** Define it as the **verified**
   citations attached to the final answer — the evidence the system actually
   stands behind after the graph walk. Extract the ordered
   `(file_path, line, verified)` triples from the citation events, filter to
   verified, dedupe preserving first occurrence, map each to a chunk id by the
   **same line-containment rule** ground truth uses, and feed that ordered list
   into the **same** metric functions, same ground truth, same `k`, same
   threshold. Log both scorings side by side per question, plus the mapped chunk
   ids, so the change is auditable.

   B2 and B3 keep their full top-5, which is their best case. B4's evidence set
   is often smaller than 5, so it gets **fewer** shots at the ground truth than
   B3. The asymmetry handicaps B4 deliberately: it can then only win by
   surfacing ground-truth evidence more precisely or earlier via the graph,
   which is exactly the capability under test. The correction was chosen in the
   direction that makes it harder for us, because that is the truthful one.

2. **Expand L3** from 3 to roughly 12 architecture-level questions on distinct
   cross-module flows, ground truth derived from code structure and verified to
   resolve against the index, committed before the re-run. Human review of the
   drafted questions is a required gate, and reviews for *fair architectural
   coverage and honest code-derived ground truth* — explicitly **not** for
   whether B4 can answer them.

3. **Leave groundedness scoring exactly as it is.** The obvious "fix" here is a
   trap. Counting only post-redaction citations would score a verified-by-
   construction set, push groundedness to ≈1.0 trivially, inflate B4's composite,
   and could flip H1 for a purely cosmetic reason. That is p-hacking in a
   bug-fix costume. Tightening the *synthesis prompt* so the model cites only
   from the allowed list is legitimate — it changes the system, not the metric —
   but it moves B4's number and must be reported as its own change, never folded
   silently into the H1 claim, and deliberately not bundled into the same run.

Expanding the question set makes the next run a **fresh pre-registration**:
expanded suite and corrected scoring both fixed before any number is seen.

### Standing commitments

- Thresholds, question set, and metric definitions are fixed before a run and
  untouched afterwards.
- We change **what gets measured** when it is objectively the wrong output. We
  do not change the pass criteria.
- Either outcome gets published. If corrected scoring clears the bar, that is a
  win earned by measuring the right thing. If it does not, this document will
  say "even counting the graph's contribution, B4 does not clear the bar."
- The goal is a true verdict, not a passing one. An honest null result with a
  diagnosed cause and precise re-open criteria is a stronger result than a tuned
  pass.

---

## Outstanding Work

The single list of what is unfinished. Items marked **▲** block the H1 re-run;
everything else is independent of it.

### Evaluation

- **▲ Score B4 on its final verified evidence set.** Criteria set 2, item 1 above.
  Without it the call graph cannot reach the metrics at all.
- **▲ Expand L3 beyond n=3** (target ~12), human-reviewed and committed before
  the re-run.
- **Judge / pairwise scoring is a stub.** Pairwise win-rate is `null` throughout,
  so the acceptance threshold on it (>60% vs B2) is unmeasured, not failed.
- **B0 is not measured** — it needs an API token. Either produce it or keep
  reporting it as unmeasured; it has no bearing on the H1 verdict.
- **B4's groundedness dip is diagnosed and partly addressed.** The agent was offering
  the model qualified names in its allowed-citation list that the guardrail rejects by
  exact match, so it was instructing the model to emit references it would then redact
  (`da2b6bc`), and that remedy has since been **reversed** — it treated the symptom by
  withdrawing the evidence, and scored worst of three arms once uncited answers stopped
  scoring perfectly. Reconciling the two symbol-matching rules (`029b9de`, entry below)
  is what actually fixed it. **Still open: the `file:line` references the model
  invents.** That is the whole of the remaining gap to the guardrail — 0.894 against
  0.95 — and it is model behaviour, not scoring. Do **not** address it by changing how
  the score is computed upward (criteria set 2, item 3). Nine-run record:
  `results/b4-citation-fix-experiment.md`.
- ~~An answer with no citations scores groundedness `1.000`~~ **— fixed.** It now
  scores `0.0`, and `dcode_eval.run` reports `answers_without_citations` beside every
  groundedness figure, because `0.0` alone cannot separate *cited nothing* from *cited
  things that all failed*. The recorded verdict does not move: all four baselines cited
  on all 16 questions in `results/eval-real/`, so the branch never executed there. It
  did fire in the variance runs, where it had been paying a free perfect score — and
  rescoring them **reverses the measured sign of the citation fix and erases its
  apparent variance reduction**, so neither is claimed. Both corrections are recorded in
  `results/b4-citation-fix-experiment.md`.
- ~~The API and the guardrail resolve a symbol by different rules~~ **— fixed, and it
  was the actual defect.** `dcode_shared.symbols` now holds one definition and both
  apply it (`029b9de`). Pre-declared before any run, because it moves the score upward.
  Nine runs across three arms: symbol-style citations survived for the first time (zero
  in all six exact-match runs, two answers in every shared-rule run), verified citations
  rose from 48–54 to 62–67, and uncited answers went back to zero — so roughly 13
  references per run had been real all along and were being deleted. Groundedness
  0.867 → 0.894. **This also reverses the earlier remedy**: withdrawing the tokens
  (`da2b6bc`) scored *worst* of the three arms once uncited answers stopped scoring
  perfectly, and only looked best while both errors were in place. Full record:
  `results/b4-citation-fix-experiment.md`.
- **A margin from one run should not be quoted to three decimals.** Repeat spread on
  unchanged synthesis code is roughly the size of the guardrail shortfall itself. Any
  future run reporting a margin should state how many repeats it averages, and how many
  repeats is itself a pre-registration decision.
- **A second corpus.** One repository, 16 questions. Nothing here generalises,
  and no wording in this document should imply otherwise.

### Retrieval and indexing

- **Python only.** The worker parses no other language.
- **Index-run provenance is schema-only.** The migrations add append-only
  `index_runs` records and `repos.current_index_run_id`, but the current ORM and
  worker do not populate or expose them. Runtime cache invalidation uses
  `index_revision`; either wire the executor record through the pipeline or
  remove the dormant schema after an explicit design decision.
- Richer graph edges beyond calls / imports / inherits / references — no type
  inference, and inherited `self.method()` calls do not resolve. See
  [Operations.md](Operations.md) for the precise coverage limits.
- Reconsider an LLM planner once retrieval quality is stable. Planning is
  currently keyword routing; answer synthesis is already optional LLM.

### Frontend

- **No surface states a single-run figure alongside its repeat spread.** The landing
  page and `/methodology` now name the pre-registered bar and the miss, bound to the
  generated snapshot and pinned by tests — the three earlier over-claims ("the guardrail
  holds it at `≥ 95%`", a `groundedness ≥ 95%` principle tag, and a metric-shaped `1.00`
  on the hero mock) are gone. What remains is smaller and real: both surfaces quote the
  recorded groundedness to three decimals with nothing saying that a repeat of the same
  code spans roughly ten times the last of those digits. Closing it means putting the
  variance into the generated snapshot, since `sync_eval_artifacts.py` reads only
  `results/eval-real/` and a hand-typed spread would be an unheld copy (§11).
- **Accessibility live regions are missing** — a regression against a previously
  closed item. A screen-reader user hears nothing as an answer streams. The
  unresolved design question is recorded in [`CLAUDE.md`](../../CLAUDE.md), since
  it needs deciding before implementing.
- The API contract is hand-mirrored into TypeScript. A compile-time test pins it;
  `openapi-typescript` is the durable fix.
- `POST /repos` is idempotent per URL, but two *simultaneous* submits can still
  create two rows. Closing that needs a uniqueness constraint on a normalised URL
  column, i.e. a migration.

### Deployment

- DNS for `dcode.odieyang.com` is unresolved; production Compose has only been
  smoke-tested locally.
- Decide whether production runs the model sidecars or depends on external model
  services.

## Known Limits

Read these as scope, not as defects.

- The default local stack runs `EMBEDDING_MODEL=stub`; the recorded result used
  real host sidecars, which is a deliberate three-command setup
  ([Operations.md](Operations.md)).
- The graph is **best-effort static evidence**: name-based analysis, no type
  inference, no MRO resolution.
- The agent planner is rule-based. Only answer synthesis is LLM-backed, and it is
  opt-in.
- The H1 decision includes no judge or pairwise metric.
- Skipped-file warnings live only in Redis on a 7-day TTL, so an older index
  honestly reports none rather than a stale count.

## Verification

What was actually run, as opposed to asserted: `make check` (lint, typecheck,
Python and frontend test suites, plus the evaluation-artifact drift check),
`make frontend-build`, `make eval-smoke`, and a real-sidecar integration smoke
against a live stack.

Not verified: visual appearance and interaction were never machine-checked —
headless screenshots do not work in the development sandbox, so the UI's
rendering has only ever been confirmed by a human in a browser. There is no
automated end-to-end test spanning the browser and a live backend.

Reproducing the real-model path: [Operations.md](Operations.md).
