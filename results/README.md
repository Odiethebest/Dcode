# Evaluation results

Four directories live here and only one is the current conclusion. This file
says which, so nobody has to guess from timestamps.

| Directory | Status | What it is |
|---|---|---|
| **`eval-real/`** | ✅ **current** | The full real-model run — Jina v2-base-code (768-dim) + BGE reranker v2-m3 + gpt-4o-mini, `k=5`, the checked-in 16-question suite. **This is the recorded H1 verdict.** Everything the UI and the docs display is generated from here. |
| `eval-real-b0/` | partial | Config only. `B0` (external code search) needs an API token this environment did not have, so B0 is **not measured** — not scored zero. It has no bearing on the H1 verdict, which rests on B2/B3/B4. |
| `eval-suite/` | superseded | An **early stub-model run**, kept deliberately. Not the current conclusion — see below. |
| `eval-smoke/` | not a result | Output of `make eval-smoke`, a single-baseline harness smoke test. Proves the harness runs; measures nothing. |

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
├── run_config.json         baselines, question set path, k, repo_id
├── provenance.json         NOT harness output — hand-recovered metadata (see below)
└── B1..B4/
    ├── metrics.json            that baseline's suite-level metrics
    ├── taxonomy_breakdown.json the same metrics split by L1/L2/L3
    └── per_question.jsonl      one row per question: retrieved chunks, answer, citations, metrics
```

`h1_report.json` is the file to read first, and it is reported verbatim.

`provenance.json` is the one file here the harness did not write. The harness
records no timestamp, so the date the artifacts display was reconstructed by
hand; it is kept out of `run_config.json` precisely so it cannot be mistaken for
something the run observed, and every field in it says **recovered**, not
**recorded**. The generator reads the date from there rather than from a file
mtime, which git does not preserve. See
[`docs/en/Honesty_Constraints.md`](../docs/en/Honesty_Constraints.md) §11.
