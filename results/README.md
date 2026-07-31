# Evaluation results

Thirteen result groups live here and only one is the current conclusion. This file
says which, so nobody has to guess from timestamps.

| Directory | Status | What it is |
|---|---|---|
| **`eval-h1-repeat3-2026-07-31/`** | ✅ **current** | B1–B4 plus the `B3.5` ablation, **3 repeats averaged**, 33 questions, uniform final-evidence scoring, three-term composite. **The recorded H1 verdict: `unsupported`** — three of the four required comparisons clear, `B4 vs B3` on L2 does not. Read `provenance.json` before quoting any margin: across the three repeats that margin ranged wider than the bar, and repeat 3 returned `supported` on its own. |
| `eval-h1-no-test-evidence-2026-07-31/` | superseded | Single run. First with test code excluded from retrieval. L3 cleared, L2 did not. Superseded by the repeated run, which is the same configuration measured three times. |
| `eval-h1-ranked-evidence-2026-07-31/` | superseded | Single run. First with graph evidence hydrated and reranked; the call graph's contribution turned positive here. Still cited test code, which the next run fixed. |
| `eval-h1-uniform-v2-2026-07-31/` | superseded | Single run. First under one scoring rule for every agent arm, and first with the `B3.5` ablation. Margins **shrank** relative to the run below, because the previous asymmetry had been inflating them. |
| `eval-h1-l3x12-2026-07-31/` | superseded | Single run. First on the 33-question suite, under the mixed `final_verified_evidence_v1` rule that scored B4 differently from B2/B3. |
| `eval-h1-bm25-2026-07-30/` | superseded | The last run on the original 16-question suite. Its B3 answered from a template and its protocol scored B4 on the same retrieval list as B3, so the call graph could not reach the metrics. |
| `eval-real/` | superseded | The full real-model H1 snapshot before that. Its sparse arm was the legacy lexical heuristic rather than BM25 and its B4 answers predate server-owned evidence IDs. Retained unchanged as historical evidence. |
| **`eval-b0-2026-07-31/`** | ✅ measured, **not reproducible** | `B0` external GitHub code search, 33 questions, **file-level only**. The one directory here whose figures cannot be regenerated from committed bytes — it queries a live external index. Not in the H1 decision. Read its `provenance.json` first; it records that the first attempt's L3 zero was our own query builder's fault, not GitHub's. |
| `eval-real-b0/` | superseded | Config only, from when `B0` had no token and was correctly recorded as unmeasured rather than zero. |
| `eval-suite/` | superseded | An **early stub-model run**, kept deliberately. Not the current conclusion — see below. |
| `eval-smoke/` | not a result | Output of `make eval-smoke`, a single-baseline harness smoke test. Proves the harness runs; measures nothing. |
| `eval-real-b4-control-prefix/` | not a verdict | B4 only — run 1 of the **original** arm (symbol tokens offered, guardrail matching exactly). |
| `eval-real-b4-citation-fix/` | not a verdict | B4 only — run 1 of arm **A**, `da2b6bc` (tokens withdrawn). |
| `b4-variance/` | not a verdict | The other six runs: `prefix-2/3`, `fix-2/3`, and `sharedrule-1/2/3` for arm **B**, `029b9de` (one shared symbol rule). |

The current H1 snapshot exercises corrected BM25, server-owned evidence IDs, the
shared agent path across B2/B3/B3.5/B4, hydrated and reranked graph evidence, and
three averaged repeats. It does not evaluate multi-turn contextualization,
Chinese questions, or KaTeX presentation, because the fixed suite is English,
single-turn and non-mathematical. Those contracts keep their unit and
integration-smoke coverage rather than being inferred from this run.

**Four things to know before quoting it.**

The verdict is a conjunction and it fails on one of four comparisons. `L3`
architecture clears against both rivals (+0.247 and +0.169, 4.9× and 3.4× the
bar) in all three repeats; `L2` cross-file clears against dense RAG (+0.136) and
falls 0.006 short against hybrid+rerank.

**The L2 margin is not stable.** Across three identical repeats it was +0.038,
+0.006 and +0.088 — a range of 0.083, wider than the 0.050 bar — and repeat 3
returned `supported` by itself. Every single-run margin in the superseded
directories above should be read with that in mind.

The composite has three terms. Groundedness was dropped on 2026-07-31 after four
runs had missed the four-term bar; since it is 1.000 for every arm, dropping it
multiplies margins by 4/3, equivalent to a 0.0375 threshold. Both readings are in
`h1_report.json`, and both say `unsupported`.

The call graph is worth +0.022 / +0.023, isolated by the `B3.5` arm. On `L3` the
agent's multi-step evidence gathering is worth +0.147 — six times as much. Most
of B4's advantage is the agent loop, not the graph.

The last three hold **one experiment, not a result to cite** — nine single-baseline B4
runs across three arms, which carry no H1 verdict. Read
[`b4-citation-fix-experiment.md`](b4-citation-fix-experiment.md) before any of those
numbers is quoted anywhere. Its conclusion **reverses the change it was opened to
measure**: arm A treated the wrong end of the defect and arm B is the remedy that
survived, and two mutually concealing errors held that up for a full round. It also
records what the runs establish about the H1 margin's own noise, which nothing had
measured before.

## Why `eval-suite/` is still here

It was produced with stub embedding and identity rerank. Stub dense retrieval
returns nothing, so B2, B3 and B4 all degenerated to the same sparse path and
scored **identically** — `Recall@5 0.1979 / MRR 0.2125 / nDCG@5 0.1917` across the
board. That artefact hid the real ladder between the baselines and made the
hypothesis untestable for a reason unrelated to the hypothesis.

It is kept rather than deleted because it is a real prior run, and because the
comparison is informative: it is what motivated criteria set 1 in
[`docs/en/Final_Report.md`](../docs/en/Final_Report.md), and meeting those
criteria is what exposed the actual obstacle. Deleting an inconvenient earlier
measurement is not something this project does.

**Do not cite it as a result.** README and Final_Report both drew their numbers
from it for a while after `eval-real/` existed; that was a real defect, fixed by
generating every displayed figure mechanically.

## Regenerating what reads from here

```bash
python3 scripts/sync_eval_artifacts.py            # rewrite every derived artifact
python3 scripts/sync_eval_artifacts.py --check    # fail if any is stale (in `make check`)
```

Targets: `apps/frontend/src/demo/evalSnapshot.ts` (read by `/methodology` and the
landing ladder) and the marker-delimited blocks in `README.md` and
`docs/{en,ch}/Final_Report*.md`.

Prose is **not** generated. After a new run, re-read the narrative copy and
correct any claim the new numbers no longer support — the tests and the check
follow the data, but the sentences around them do not.

## Layout of a run directory

```text
eval-h1-repeat3-2026-07-31/
├── h1_report.json          the verdict, plus `four_term`, `repeats` and each repeat's own verdict under `per_repeat`
├── suite_summary.json      whole-suite metrics per arm, averaged across repeats
├── run_config.json         arms, question set, k, repeats, scoring protocol, composite terms, BM25 config, corpus revision
├── provenance.json         NOT harness output — externally observed metadata (see below)
├── repeat-1..3/            each repeat complete and independent, with its own h1_report.json
└── B1..B4, B3.5/           the mean across repeats; per-question rows carry __min/__max per metric
    ├── metrics.json            that arm's suite-level metrics
    ├── taxonomy_breakdown.json the same metrics split by L1/L2/L3
    └── per_question.jsonl      one row per question, averaged, with one real sampled transcript
```

A repeated run's top-level `B*/` rows are averages, so their `answer` text is one
real sample rather than a mean — `sampled_from_repeat` records which. Metrics
carry `__min` and `__max` alongside the mean, because a question that flipped
between repeats and one that was stable should not read the same.

Under `uniform_final_verified_evidence_v2` every per-question row carries three scorings
side by side — `candidate_*` (retrieved top-k), `final_evidence_*` (verified
citations the answer stands behind), and the unprefixed official metric — plus
`scoring_source`, `structural_evidence_chunk_ids`, and
`new_gt_hits_from_structural_evidence`. That last field is how the call graph's
contribution is counted rather than assumed.

`h1_report.json` is the file to read first, and it is reported verbatim.

`provenance.json` is the one file here the harness did not write. The current
harness records the BM25 formula, tokenizer, fields, parameters, and
`corpus_revision` directly in `run_config.json`; it still writes no timestamp,
model names, repo commit, or service health observations. Those externally
observed facts stay in provenance precisely so they cannot be mistaken for
harness output. The generator reads that metadata from committed bytes, never
from a file mtime or the wall clock. The older `eval-real/` provenance also
records the sparse implementation recovered for that historical run. See
[`docs/en/Honesty_Constraints.md`](../docs/en/Honesty_Constraints.md) §11.
