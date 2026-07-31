# Dcode Final Report

## Summary

Dcode is a structure-aware code understanding stack built around four runtime surfaces:

- async indexing (`POST /api/v1/repos` → worker pipeline)
- internal retrieval / graph APIs
- SSE-based agent answers with grounded citations
- an evaluation harness and comparison UI

As of **2026-07-31**, the repository delivers a complete local vertical slice:

- a real indexing pipeline for Python repositories
- retrieval and graph lookup endpoints
- self-hosted embedding and reranker sidecars, exercised on a full real-model run
- a working agent loop with 11 tools
- bounded multi-turn follow-ups, bilingual caller/callee routing, same-language
  answers, and server-owned evidence IDs
- a single exploration workbench whose citations open real indexed source and
  walk the call graph, plus a `/methodology` page reporting this evaluation
- a production-shaped Docker Compose package with static frontend serving

**Read this report for the verdict.** H1 is recorded **unsupported** on the
real-model run. B4 cleared the bar against both rivals on cross-file questions
and missed on architecture questions by 0.005. The evaluation section below gives
the numbers, the scoring rule the verdict turns on, how much of B4's margin the
call graph actually accounts for (little), and what would re-open the question.
The claim this project cares about most is not that H1 passed — it is that the
answer is honest and checkable.

The current recorded run uses the 33-question suite (`L3` expanded from 3 to 12),
corrected Okapi BM25, the server-owned evidence-ID path, and a shared agent
synthesis path for B3 and B4. The suite is still English, single-turn,
non-mathematical, and drawn from one repository, so it does not replace the
dedicated bilingual, multi-turn, or KaTeX tests and it generalises to nothing.

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
- bounded client-history contextualization for follow-up questions
- English and Chinese caller/callee intent routing
- optional LLM answers in the current question's language
- request-local server-owned evidence IDs rather than model-invented symbol tokens
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
- safe Markdown rendering with KaTeX math support, including normalization of
  common LaTeX delimiters outside code spans and fences.
- a branded repository-native SVG favicon shared by the built frontend.
- nginx-hosted static frontend image
- `docker-compose.prod.yml` with frontend-only public exposure and `/api/*` proxying

## Evaluation Snapshot

The recorded suite uses 33 `requests` questions — 16 manually curated plus a
17-question `graph_reverse` expansion — measured on a full real-model run. Every
figure in this section is generated from the results directory by
`scripts/sync_eval_artifacts.py` and is not transcribed by hand; `make check`
fails if the two diverge.

`B2` and `B3` are scored on their retrieved top-`k`; `B4` is scored on its
ordered verified final evidence. That difference is the protocol
`final_verified_evidence_v1`, and the verdict turns on it — see *Reading the
result honestly* immediately below the tables.

Aggregate metrics:

<!-- BEGIN generated: eval-suite-metrics -->

| Baseline | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---|
| `B1` BM25 sparse | 0.369 | 0.473 | 0.334 | 1.000 |
| `B2` Dense RAG | 0.340 | 0.395 | 0.286 | 1.000 |
| `B3` Hybrid + rerank | 0.401 | 0.634 | 0.418 | 1.000 |
| `B4` Dcode (hybrid + call graph + agent) | 0.448 | 0.763 | 0.494 | 1.000 |

Source: `results/eval-h1-l3x12-2026-07-31/` · verdict written 2026-07-31 · psf/requests · k=5 · embedding Jina v2-base-code (768-dim) · reranker BGE reranker v2-m3 · synthesis gpt-4o-mini

The date is **committed provenance, not harness output** — the harness writes no timestamp. Its observation basis and limits are recorded in `results/eval-h1-l3x12-2026-07-31/provenance.json`.

<!-- END generated: eval-suite-metrics -->

H1 verdict:

<!-- BEGIN generated: eval-h1-verdict -->

**Decision: `unsupported`**

H1 is supported only if B4 beats **both** B2 and B3 by at least `0.050` composite points on **both** L2 and L3.

| Level | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | Cleared |
|---|---:|---:|---:|---:|---:|---:|---|
| `L2` cross-file | 16 | 0.484 | 0.618 | 0.701 | +0.217 | +0.083 | yes |
| `L3` architecture | 12 | 0.411 | 0.463 | 0.508 | +0.097 | +0.045 | no |

<!-- END generated: eval-h1-verdict -->

Recall by question level — the ladder that did hold up:

<!-- BEGIN generated: eval-level-ladder -->

| Level | n | `B1` Recall@5 | `B2` Recall@5 | `B3` Recall@5 | `B4` Recall@5 |
|---|---:|---:|---:|---:|---:|
| `L1` single-hop | 5 | 0.600 | 1.000 | 1.000 | 1.000 |
| `L2` cross-file | 16 | 0.376 | 0.293 | 0.367 | 0.450 |
| `L3` architecture | 12 | 0.263 | 0.129 | 0.196 | 0.217 |

<!-- END generated: eval-level-ladder -->

### Reading the result honestly

**H1 is unsupported, by 0.005 on one level.** B4 now clears the +0.05 bar against
both B2 and B3 on cross-file questions — the first run in which it has cleared
anything against B3 — and misses on architecture questions with a margin of
+0.045 where +0.050 was required. The threshold, the question set, and the metric
definitions were fixed before the run and have not been touched since.

A near miss is still a miss. It is not "effectively supported", and the honest
summary of this run is not that H1 nearly passed but that **H1 is not resolved at
this precision**, for the three reasons below.

**The verdict is protocol-sensitive, and the alternative rule flips it.** Under
the pre-registered `final_verified_evidence_v1`, B2 and B3 are scored on their
retrieved top-k while B4 is scored on its ordered verified final evidence — two
different rules. The harness also computes B3's own final-evidence score, so the
symmetric comparison is available:

| Level | B4 − B3, official (mixed) | B4 − B3, symmetric (both on final evidence) |
|---|---:|---:|
| `L2` | +0.083 ✅ | +0.057 ✅ |
| `L3` | +0.045 ❌ | +0.051 ✅ |

Symmetric scoring would return `supported`. **It is not adopted, and it is not
the verdict.** Choosing a scoring rule after seeing that it changes the outcome is
the exact failure this project pre-registers against. The pre-registered rule
reports `unsupported` and that is what stands. The alternative is published
because a reader who found it independently would rightly ask why it was missing,
and because the next run must pre-register **one** rule for every arm.

**The pre-registered justification for that asymmetry is falsified by this run.**
Criteria set 2 argued the rule "handicaps B4 deliberately", because B4's evidence
set is usually smaller than five and therefore gets fewer shots at the ground
truth. The data says the opposite: B4's verified final evidence scored *higher*
than its own candidate top-5 — recall 0.448 against 0.401, MRR 0.763 against
0.634. Selecting evidence precisely is worth more than having five slots. The
rule helped B4. That reasoning was wrong, it was wrong in the direction that
flatters us, and it is corrected here rather than quietly dropped.

**The call graph's own contribution is small, and is now measured rather than
inferred.** Structural evidence — graph or outline results not already present in
the hybrid top-k — produced **4 new ground-truth hits across 3 of 33 questions**.
B4's margin over B3 therefore cannot be attributed to the call graph. What
separates the two arms is mostly the agent's multi-step evidence *selection*, and
nothing in this run distinguishes that from the graph itself. The ablation that
would separate them (`B3.5`: same agent and `read_file` loop, call-graph and
reference tools disabled) does not exist yet.

**The corrected BM25 path stays measured.** The run records the formula,
tokenizer, document fields, parameters, and corpus revision. Sparse `B1` again
posts a higher MRR than dense `B2` (0.473 against 0.395) and a higher L3 recall
than any other rung, which is a real property of this corpus and not an artefact
of a small L3 any more.

**Groundedness is at the ceiling for every arm, and for two of them that is not a
measurement.** `B1` and `B2` answer from a template whose groundedness is the
constant `1.0`; only `B3` and `B4` run the real verifier. Since groundedness is
one of the four equally weighted composite terms, a quarter of B2's composite is
awarded rather than earned, and every `B4 vs B2` margin in the table above
inherits that. Closing it needs a `dense_only` agent mode so B2 shares the
synthesis and citation path; until then the B2 column should be read as a
retrieval comparison with a constant attached.

**L3 is less fragile than it was, and still fragile.** At n=12 one question moves
the level composite by up to 0.083 — larger than the 0.005 by which L3 missed.
`q-033` alone scored −0.156 for B4 against B3. Getting a single question's weight
below the 0.05 decision margin requires n > 20.

## What Worked

- The repo now has a defensible vertical slice rather than disconnected stubs.
- Real embedding and reranker clients are implemented behind environment-driven sidecar boundaries.
- Graph coverage has moved beyond module imports with best-effort intra-repo call edges.
- `repo_id` isolation, caches, and internal-route protection are enforced in code and tests.
- The production packaging path is now explicit and locally smoke-tested.
- Citation verification demonstrably does work: it catches unverifiable
  references and strips them from delivered answers. The current evidence-ID
  run clears the guardrail without changing the pre-redaction scoring rule,
  while the superseded failures remain archived rather than erased.
- Every number a user or reviewer sees is generated from the results directory.
  The UI, this report, and the README cannot disagree without `make check`
  failing.
- The hypothesis is finally *measurable*. Three consecutive runs failed for three
  different reasons — stub models made the arms identical, then the harness
  scored a list the graph never touched, and only now can the graph's own
  contribution be counted at all. That the count came out small is a result;
  being unable to count it was not.

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

**Criteria set 1b (met on 2026-07-30).** Replace the legacy sparse heuristic with
recorded Okapi BM25, run the full B1–B4 suite through the server-owned evidence-ID
protocol, and keep the metric definitions fixed. It improved B1 retrieval and
brought B4 above the groundedness guardrail, while H1 remained unsupported
because B4's scored retrieval still tied B3 by construction. That snapshot is
retained at `results/eval-h1-bm25-2026-07-30/` and is now superseded.

**Criteria set 2 (met on 2026-07-31).** Score B4 on its verified final evidence,
give B3 the same agent synthesis path, and expand L3 from 3 to 12. That is the
current run.

**What that run showed.** The obstacle the previous run diagnosed is gone: B4's
scored evidence is no longer B3's retrieval list, so the graph could finally
reach the metrics. B4 cleared L2 against both rivals and missed L3 by 0.005 — and
three things became visible that no earlier run could have shown.

The first is that **the correction's own justification was wrong.** Scoring B4 on
its smaller evidence set was pre-registered as a handicap; measured, it is an
advantage, because precise selection beats having five slots.

The second is that **the graph is not what is producing B4's margin.** Now that
structural evidence is tracked by origin, it can be counted: 4 new ground-truth
hits across 3 of 33 questions. The hypothesis under test is finally measurable
and its measured effect is small.

The third is that **the verdict depends on a scoring rule that was only ever
pre-registered for one arm.** Applying the same rule to B3 flips L3 from fail to
pass. Fixing that is now the top item for the next run, and it must be fixed
*before* the run, not chosen after.

## H1 Decision

**H1 remains unsupported** on the full real-model run — see the generated verdict
table above for the margins, read straight from `h1_report.json`. L2 cleared, L3
missed by 0.005.

The decision is no longer scoped to a muted baseline, and no longer scoped to an
unmeasurable comparison. Real embeddings, a real reranker, a shared synthesis
path for B3 and B4, and a scoring rule that reaches the graph's output were all
in place, and B4 still did not clear both levels. What changed is the *reason*
again: the obstacle is no longer "the harness cannot see the graph" but "the
graph contributes little, and what margin exists is partly an artefact of scoring
the two arms by different rules."

### Criteria set 2 — outcome

Recorded as tested, not as intended.

1. **Score B4 on its final evidence set — done, and the reasoning behind it was
   falsified.** The groundedness verifier attaches the resolved chunk ID and
   evidence origin to each citation event. The harness filters to verified
   citations with a server-resolved chunk ID, dedupes by chunk while preserving
   answer order, and feeds that list into the **same** metric functions, same
   ground truth, same `k`, same threshold, capped at `k` before MRR as well as
   Recall/nDCG. Candidate, final-evidence and official scorings are logged side
   by side per question, with structural origins and new structural GT hits.

   The pre-registration said: "B2 and B3 keep their full top-5, which is their
   best case … the asymmetry handicaps B4 deliberately." **That was wrong.** B4's
   final evidence outscored its own top-5 on every retrieval metric, so the rule
   was an advantage. The prediction is left visible here rather than edited out,
   because a pre-registration you are allowed to silently revise is not one.

2. **Expand L3 — done.** 17 questions added (8 cross-file `L2`, 9 architecture
   `L3`), suite now `L1` 5 / `L2` 16 / `L3` 12 = 33. Every anchor was verified to
   resolve 1:1 against the live index using the resolver alone, before any
   baseline ran; the file was frozen by commit `ae47419` with its sha256 recorded
   in the run's `provenance.json`; the human review gate was held. Nothing was
   removed, so the three pre-existing overlapping pairs still dilute the strata.
   The batch is labelled `source: graph_reverse` because it was reverse-
   constructed from this corpus's indexed call relationships — a construction
   that cannot contain a flow the graph misses, and therefore favours B4. That
   bias is recorded, not corrected.

3. **Leave groundedness scoring exactly as it is — held.** The obvious "fix" here
   is a trap. Counting only post-redaction citations would score a verified-by-
   construction set, push groundedness to ≈1.0 trivially, inflate B4's composite,
   and could flip H1 for a purely cosmetic reason. That is p-hacking in a bug-fix
   costume. The scoring rule was not touched.

### Criteria set 3 — to re-open H1

Fixed here, before the next run, in the same spirit as the sets above.
**Items 1–3 are implemented and pre-registered; no suite has been run under
them.** Everything in this subsection was committed while the current recorded
verdict was still the 2026-07-31 v1 run, so no number from the new protocol
influenced how the protocol was defined.

1. **Implemented — one scoring rule for every arm.** The official metric is
   **verified final evidence**, applied identically to `B2`, `B3`, `B3.5` and
   `B4`. Protocol id `uniform_final_verified_evidence_v2`.

   The rule was chosen over candidate top-`k` because top-`k` scores a list the
   graph never touches, which is the defect criteria set 2 was opened to fix;
   reverting to it would un-fix it. `B0` and `B1` answer from a template, emit no
   citation events, and therefore cannot be scored by this rule — they stay
   retrieval references on candidate top-`k`, and they are **not** in the H1
   decision, which reads `B2`/`B3`/`B4` only. Every row still records
   `candidate_*` and `final_evidence_*` side by side, so the other scoring
   remains auditable without being selectable after the fact.

   Stated plainly, because it is the point: under v1 this run's `L3` margin was
   +0.045 and under symmetric scoring +0.051, straddling the 0.05 bar. **Fixing
   the rule is expected to move the verdict, and the direction it moves is not
   knowable until the suite runs.** That is why it is fixed first.

2. **Implemented — `dense_only` agent mode for B2.** `B2` now answers through the
   same agent, prompt, model, citation protocol and groundedness verifier as
   `B4`, over dense-only retrieval. Its groundedness becomes a measurement rather
   than the template constant `1.0` that was a quarter of its composite, and it
   can produce the verified final evidence item 1 requires.

   The retrieval mode travels in the `search_code` **tool arguments**, not as
   ambient state. The tool cache key is `(tool, repo_id, args)`, so a mode kept
   outside the args would have let B2's dense search and B3's hybrid search share
   one cache entry — the arms would have been silently identical.

3. **Implemented — `B3.5` diagnostic arm.** `B4` with `find_definition`,
   `find_references`, `get_call_neighbors`, `get_dependencies` and
   `get_dependents` disabled; `read_file` and `get_file_outline` retained, and
   everything else — model, prompt, hybrid retrieval, step budget, guardrail —
   held identical. So:

   | Contrast | What it measures |
   |---|---|
   | `B4 − B3` | the whole agent system |
   | `B4 − B3.5` | the call graph on its own — **the actual hypothesis** |
   | `B3.5 − B3` | multi-step reading, without a graph |

   `B3.5` is reported under `diagnostics` in `h1_report.json` and is **excluded
   from the pass criteria**. Adding an arm to the decision rule would be changing
   the pass criteria.

   Keeping `read_file` and `get_file_outline` in `B3.5` is deliberate and is the
   direction that costs us: a weakened no-graph arm would inflate `B4 − B3.5` and
   make the graph look better than it is. An early draft truncated the walk at
   the first blocked tool, which would have denied `B3.5` the outline tool purely
   through branch ordering; that is fixed and pinned by a test.
4. **Unify evidence ordering across sources.** Hybrid chunks carry reranker
   scores; graph results enter the context in tool-return order. Score the union
   with one query-aware ranking, with a shared context budget and a shared `k`
   for both arms, and keep `graph_distance` as a recorded diagnostic that does
   **not** enter the ranking — a tunable graph prior would be a hyper-parameter
   fitted on the evaluation set.
5. **Raise `L3` toward n ≈ 22** so one question's weight falls below the 0.05
   decision margin. Do this with a **second corpus** — the indexed
   `encode/httpx` — not with more Requests questions, which restate the same
   flows. This needs per-question repository binding first: the harness records a
   single `repo_id_override` and reads one `index_revision`.
6. **Raise `max_steps` or narrow the expansion.** B4 saturates the 8-step budget,
   so `get_file_outline` is effectively unreachable and the walk is truncated by
   the cap rather than by the planner.

### Standing commitments

- Thresholds, question set, and metric definitions are fixed before a run and
  untouched afterwards.
- We change **what gets measured** when it is objectively the wrong output. We
  do not change the pass criteria.
- Either outcome gets published, and so does a pre-registered prediction that
  turns out to be wrong. This run falsified one of ours and it is recorded above.
- When two defensible scoring rules disagree, the pre-registered one is the
  verdict and the other is published beside it. Picking the winner afterwards is
  not an option that exists.
- The goal is a true verdict, not a passing one. An honest null result with a
  diagnosed cause and precise re-open criteria is a stronger result than a tuned
  pass.

---

## Outstanding Work

The single list of what is unfinished. Items marked **▲** block the next
graph-sensitive H1 re-run; everything else is independent of it.

### Evaluation

- ~~Score B4 on its final verified evidence set~~ **— done and measured.** See
  criteria set 2 above: it worked, and the pre-registered claim that it would
  handicap B4 was falsified by the result.
- ~~Expand L3 beyond n=3~~ **— done, n=12.** Human-reviewed, resolver-verified,
  and frozen with a checksum before any baseline ran.
- ~~One scoring rule for every arm~~ · ~~`dense_only` mode for B2~~ ·
  ~~`B3.5` diagnostic arm~~ **— all three implemented and pre-registered, awaiting
  a run.** Protocol `uniform_final_verified_evidence_v2`; see criteria set 3.
  **The recorded verdict above predates them**, so it remains the current result
  until a suite runs under the new protocol. Expect it to move: the rule change
  alone straddles the bar `L3` missed by.
- **▲ Run the suite under `uniform_final_verified_evidence_v2`.** The blockers
  are cleared; nothing about the new protocol is measured until this happens.
  `B1` remains a retrieval reference outside the decision — giving it a
  `sparse_only` mode would make every displayed row one system with one variable,
  but it would also stop `B1` being a pure retrieval baseline, so it is left as a
  deliberate open choice rather than done quietly.
- **Unify evidence ordering across sources**, with `graph_distance` recorded but
  excluded from the ranking. Criteria set 3 item 4.
- **`max_steps = 8` is saturated by B4's expansion**, so `get_file_outline` is
  effectively unreachable and the walk ends at the cap rather than at the
  planner's decision.
- **Judge / pairwise scoring is a stub.** Pairwise win-rate is `null` throughout,
  so the acceptance threshold on it (>60% vs B2) is unmeasured, not failed.
- **B0 is not measured** — it needs an API token. Either produce it or keep
  reporting it as unmeasured; it has no bearing on the H1 verdict.
- ~~Re-run the evidence-ID protocol across B1–B4~~ **— completed.** The earlier
  groundedness dip was diagnosed on the pre-evidence-ID protocol. The
  agent offered qualified names that the exact-match guardrail rejected;
  withdrawing those names (`da2b6bc`) treated the symptom and scored worst once
  uncited answers stopped scoring perfectly. The shared symbol rule (`029b9de`,
  entry below) was the measured remedy. The server-owned evidence-ID path now
  has a complete current run and clears the guardrail without changing the
  score. The nine-run record remains the authority for the historical failure:
  `results/b4-citation-fix-experiment.md`.
- ~~An answer with no citations scores groundedness `1.000`~~ **— fixed.** It now
  scores `0.0`, and `dcode_eval.run` reports `answers_without_citations` beside every
  groundedness figure, because `0.0` alone cannot separate *cited nothing* from *cited
  things that all failed*. Both complete H1 snapshots have citations on every
  question, so the branch does not affect either verdict. It did fire in the
  variance runs, where it had been paying a free perfect score — and
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
- **▲ This run's margins are single-run and stochastic, and that now matters.**
  The previous verdict was structurally fixed by the B3/B4 retrieval tie, so
  repeats could not have changed it. This one turns on 0.005 with LLM synthesis
  in the loop and no repeats, so the margin's own noise is unmeasured and could
  exceed the gap. Any future run reporting a nonzero margin must state how many
  repeats it averages, and the repeat count is itself a pre-registration
  decision.
- **The suite's strata are not independent.** Three pre-existing pairs share
  ground truth at 1.00, 0.75 and 0.50 (`q-006`/`q-014`, `q-009`/`q-016`,
  `q-010`/`q-015`), so every L3 question in the original set restates an L2
  question. "Cleared on both L2 and L3" is therefore weaker than two independent
  tests. The 17 new questions do not add to this — their maximum overlap is 0.33
  both internally and against the original set — but they dilute it rather than
  remove it.
- **17 of 33 questions were reverse-constructed from the indexed call graph**
  (`source: graph_reverse`). A suite built from the system's own graph output
  cannot contain a flow that graph misses, so the documented blind spots — no
  type inference, unresolved inherited `self.method()` calls — are absent by
  construction, which favours B4. Recorded rather than corrected; a future batch
  should deliberately include chains that traverse those blind spots.
- **A second corpus.** One repository, 33 questions. Nothing here generalises,
  and no wording in this document should imply otherwise. `encode/httpx` is
  already indexed; per-question repository binding is the blocker.

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

- **The UI reports one recorded run, not a universal guarantee.** Landing and
  `/methodology` bind both the pre-registered bar and the measured outcome to the
  generated snapshot. Repeat variance is not displayed because the historical
  variance experiment used a different citation protocol; any future comparable
  repeat series must be committed beside the official run before it is shown.
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
- `B1` and `B2` answer from a template, so their groundedness is the constant
  `1.0` rather than a measurement, and they emit no citation events. This is
  scope, but it is load-bearing scope: groundedness is a quarter of the composite
  the H1 decision is computed from.
- The two levels the H1 rule conjoins are not independent samples; see the
  ground-truth overlap entry under Outstanding Work.
- Skipped-file warnings live only in Redis on a 7-day TTL, so an older index
  honestly reports none rather than a stale count.

## Verification

What was actually run, as opposed to asserted: `make check` (lint, typecheck,
Python and frontend test suites, plus the evaluation-artifact drift check),
`make frontend-build`, `make eval-smoke`, and a real-sidecar integration smoke
against a live stack.

On 2026-07-31, immediately around the recorded run, the Docker stack and both
host model sidecars were healthy: the embedding sidecar returned a 768-dimension
vector for a one-text request, and the reranker returned two clearly separated
scores for a two-passage request. The harness logged zero API or agent errors
across all four baselines. A direct two-mode probe against `/internal/query`
confirmed the B3/B4 control actually differentiates — `hybrid_only` issued one
tool call, `full` issued eight — rather than being a flag the agent ignores.

An earlier attempt at the same run was aborted during B3 and its partial output
deleted: Redis still held agent tool-result entries written about two hours
earlier, before the current agent code existed, and those could have supplied
graph results lacking the `chunk_id` the new scoring protocol reads. The cache
was flushed and the whole suite rerun from B1. The recorded directory contains
only the complete rerun. This is in `provenance.json` too, because a reader
reproducing the run needs to know the cache state it assumed.

Not verified: visual appearance and interaction were never machine-checked —
headless screenshots do not work in the development sandbox, so the UI's
rendering has only ever been confirmed by a human in a browser. There is no
automated end-to-end test spanning the browser and a live backend.

Reproducing the real-model path: [Operations.md](Operations.md).
