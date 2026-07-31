# Evaluation results

Seven directories live here and only one is the current conclusion. This file
says which, so nobody has to guess from timestamps.

| Directory | Status | What it is |
|---|---|---|
| **`eval-real/`** | ✅ **current** | The full real-model run — Jina v2-base-code (768-dim) + BGE reranker v2-m3 + gpt-4o-mini, `k=5`, the checked-in 16-question suite. **This is the recorded H1 verdict.** Its sparse arm was the legacy lexical heuristic, not BM25; generated surfaces label it accordingly. |
| `eval-real-b0/` | partial | Config only. `B0` (external code search) needs an API token this environment did not have, so B0 is **not measured** — not scored zero. It has no bearing on the H1 verdict, which rests on B2/B3/B4. |
| `eval-suite/` | superseded | An **early stub-model run**, kept deliberately. Not the current conclusion — see below. |
| `eval-smoke/` | not a result | Output of `make eval-smoke`, a single-baseline harness smoke test. Proves the harness runs; measures nothing. |
| `eval-real-b4-control-prefix/` | not a verdict | B4 only — run 1 of the **original** arm (symbol tokens offered, guardrail matching exactly). |
| `eval-real-b4-citation-fix/` | not a verdict | B4 only — run 1 of arm **A**, `da2b6bc` (tokens withdrawn). |
| `b4-variance/` | not a verdict | The other six runs: `prefix-2/3`, `fix-2/3`, and `sharedrule-1/2/3` for arm **B**, `029b9de` (one shared symbol rule). |

The recorded H1 snapshot and the nine-run citation experiment both predate the
server-owned evidence-ID protocol, bounded multi-turn contextualization,
same-language answer contract, and KaTeX presentation changes now on the branch.
Those changes have unit and integration-smoke coverage, but no complete
replacement evaluation. The committed `unsupported` verdict therefore remains
the project result while being explicitly historical rather than a measurement
of every current interaction behavior.

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
eval-real/
├── h1_report.json          the verdict: decision, threshold, per-level composites and margins
├── suite_summary.json      whole-suite metrics per baseline
├── run_config.json         baselines, question set path, k, repo_id; new runs also record BM25 config and corpus revision
├── provenance.json         NOT harness output — hand-recovered metadata (see below)
└── B1..B4/
    ├── metrics.json            that baseline's suite-level metrics
    ├── taxonomy_breakdown.json the same metrics split by L1/L2/L3
    └── per_question.jsonl      one row per question: retrieved chunks, answer, citations, metrics
```

`h1_report.json` is the file to read first, and it is reported verbatim.

`provenance.json` is the one file here the harness did not write. The harness
recorded neither a timestamp nor, for this archived run, the sparse
implementation. Both facts were reconstructed and are kept out of
`run_config.json` precisely so they cannot be mistaken for observations made by
the run; every recovered field says so. Future runs write the BM25 formula,
tokenizer, fields, parameters, and `corpus_revision` directly into
`run_config.json`. The generator reads recovered metadata from committed bytes,
never from a file mtime, which git does not preserve. See
[`docs/en/Honesty_Constraints.md`](../docs/en/Honesty_Constraints.md) §11.
