# Evaluation results

Nine result groups live here and only one is the current conclusion. This file
says which, so nobody has to guess from timestamps.

| Directory | Status | What it is |
|---|---|---|
| **`eval-h1-l3x12-2026-07-31/`** | ✅ **current** | The complete B1–B4 real-model run on the **33-question** suite (`L3` expanded 3 → 12) under scoring protocol `final_verified_evidence_v1`, with B3 and B4 sharing one agent synthesis path. Same models, same `k=5`, same index as the run below. **This is the recorded H1 verdict: `unsupported`,** with L2 cleared and L3 short by 0.005. |
| `eval-h1-bm25-2026-07-30/` | superseded | The previous complete B1–B4 real-model run, on the original 16-question suite. Its B3 answered from a template rather than the agent, and its protocol scored B4 on the same retrieval list as B3, so the call graph could not reach the metrics. Retained unchanged as historical evidence. |
| `eval-real/` | superseded | The full real-model H1 snapshot before that. Its sparse arm was the legacy lexical heuristic rather than BM25 and its B4 answers predate server-owned evidence IDs. Retained unchanged as historical evidence. |
| `eval-real-b0/` | partial | Config only. `B0` (external code search) needs an API token this environment did not have, so B0 is **not measured** — not scored zero. It has no bearing on the H1 verdict, which rests on B2/B3/B4. |
| `eval-suite/` | superseded | An **early stub-model run**, kept deliberately. Not the current conclusion — see below. |
| `eval-smoke/` | not a result | Output of `make eval-smoke`, a single-baseline harness smoke test. Proves the harness runs; measures nothing. |
| `eval-real-b4-control-prefix/` | not a verdict | B4 only — run 1 of the **original** arm (symbol tokens offered, guardrail matching exactly). |
| `eval-real-b4-citation-fix/` | not a verdict | B4 only — run 1 of arm **A**, `da2b6bc` (tokens withdrawn). |
| `b4-variance/` | not a verdict | The other six runs: `prefix-2/3`, `fix-2/3`, and `sharedrule-1/2/3` for arm **B**, `029b9de` (one shared symbol rule). |

The current H1 snapshot exercises corrected BM25, the server-owned evidence-ID
path, the shared B3/B4 synthesis control, and B4 final-evidence scoring. It does
not evaluate multi-turn contextualization, Chinese questions, or KaTeX
presentation because the fixed suite contains English, single-turn,
non-mathematical questions. Those interaction contracts retain their unit and
integration-smoke coverage rather than being inferred from this run.

**Two things to know before quoting the current run.** Its verdict flips if B3 is
scored by B4's rule instead of its own — the pre-registered mixed rule reports
`unsupported`, the symmetric rule would report `supported`, and the difference is
0.006 on L3. And the call graph, whose contribution is measured here for the
first time, accounts for only 4 new ground-truth hits across 3 of 33 questions.
Both are recorded in that run's `provenance.json` and explained in
[`docs/en/Final_Report.md`](../docs/en/Final_Report.md). Neither is a reason to
avoid citing the run; both are reasons to cite it precisely.

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
eval-h1-l3x12-2026-07-31/
├── h1_report.json          the verdict: decision, threshold, scoring protocol, per-level composites and margins
├── suite_summary.json      whole-suite metrics per baseline, official plus candidate and final-evidence views
├── run_config.json         baselines, question set path, k, repo_id, scoring protocol, BM25 config, corpus revision
├── provenance.json         NOT harness output — externally observed metadata (see below)
└── B1..B4/
    ├── metrics.json            that baseline's suite-level metrics
    ├── taxonomy_breakdown.json the same metrics split by L1/L2/L3
    └── per_question.jsonl      one row per question: retrieved chunks, answer, citations, metrics
```

Under `final_verified_evidence_v1` every per-question row carries three scorings
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
