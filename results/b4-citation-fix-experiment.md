# B4 citation-token fix — paired measurement, 2026-07-30

What `da2b6bc` (*stop offering citations the guardrail rejects by construction*) did to
B4's groundedness, measured rather than predicted. **Neither run here is a verdict.**
`results/eval-real/` remains the recorded H1 result and was not touched.

## Why a control run exists at all

The first instinct was to compare the post-fix run against `results/eval-real/`'s
`0.9158`. That comparison is invalid, and finding out why is the main result of this
file: the archived figure is a **single sample taken on another day from a process
that recorded none of its conditions**, and answer synthesis runs at
`temperature=0.1`, not `0`. So a second run of the *unchanged* code was needed to
learn what a repeat costs before any difference could be attributed to the change.

## Design

Both arms in one session, against one live stack, differing only in the agent image:

| Held constant | Value, checked rather than assumed |
|---|---|
| Corpus | repo_id `2543893e-0965-4be7-ac45-5a8e38600bc0`, 726 chunks, all 726 carrying a vector |
| Question set | `apps/eval/src/dcode_eval/questions/data/questions.jsonl`, 16 questions |
| `k` | 5 |
| Embedding sidecar | `jinaai/jina-embeddings-v2-base-code`, `max_seq_length=1024`, host `:8002` |
| Reranker sidecar | `BAAI/bge-reranker-v2-m3`, `max_length=512`, host `:8003` |
| Synthesis | `SYNTHESIS_MODEL=gpt-4o-mini`, read from the running agent container |
| Varied | the agent image only — verified per arm by grepping the *container's* copy of `graph.py` and `llm.py` |

**How strong this record is.** The harness on this branch writes no `run_record.json`,
so none of the above is harness output. Each row was observed in-session by querying
the container or the database at run time and is written down here by hand. Nothing
mechanical holds it: re-reading this file cannot re-establish it. That is weaker than
an executor record and is not being presented as one.

The image check is the one that could not be skipped. `make up` runs a baked image, so
a source edit does not reach the agent until it is rebuilt; both arms were confirmed
inside the container (`if "." in symbol` present/absent, the new prompt rule
absent/present) before their run started.

## Results

| Run | Code | Session | groundedness | redaction markers | verified citations |
|---|---|---|---|---:|---:|
| `results/eval-real/` (B4) | pre-fix | 2026-07-28 | 0.9158 | 14 | 53 |
| `results/eval-real-b4-control-prefix/` | pre-fix | this one | **0.8863** | 17 | 54 |
| `results/eval-real-b4-citation-fix/` | post-fix | this one | **0.8946** | 10 | 43 |

Recall@5, MRR and nDCG@5 are **byte-identical across all three** — retrieval is
deterministic here and only synthesis varies, which is what makes the paired design
work at all.

```
same code, two runs (noise floor)   0.9158 → 0.8863   spread 0.0295
the change, controlled              0.8863 → 0.8946   effect +0.0083
the invalid comparison              0.9158 → 0.8946          −0.0212
```

## What this establishes

**The effect on aggregate groundedness is unresolvable.** The noise floor is 3.5× the
effect. The controlled sign is positive, and on one pair per arm that sign carries no
weight either.

**Two apparent regressions were noise, not the change.** Read against the archive,
q-016 looked like `1.000 → 0.714` and q-007 like `0.800 → 0.750`. Both were already at
the lower value in the control, on unchanged code. Only four questions moved between
control and treatment: q-010 `+0.200`, q-014 `+0.250`, q-012 `−0.250`, q-015 `−0.067`.

**The observable that did move is the redaction count**, 17 → 10, with symbol-style
citations at zero in every answer of both arms. Suggestive and not established: the
two same-code runs differ by 3 on this counter, so a 7-point drop sits outside that
range — a range drawn from two samples.

**The fix is kept on mechanism, not on this number.** The agent was placing qualified
names in the 'Allowed citations' list that `_verify_symbol` rejects by exact match, so
it was instructing the model to emit references it would then redact. That defect is
established by reading the code and the index (719 of 724 symbols carry a `src.` /
`tests.` prefix, no short-form row exists); it does not depend on this measurement.
Fewer redaction scars in delivered answers is a product improvement whether or not the
fraction moves.

**The 0.95 guardrail is met by neither arm** — 0.8863 and 0.8946, not close. This
route does not reach it.

## What this says about the figure the UI displays

`0.916` is displayed to three decimals in the report, the landing page and
`/methodology`, against a bar of `0.95`. Its run-to-run spread on unchanged code is
**0.0295, and had never been measured.** Of the three samples now in hand it is the
highest.

The direction survives — 0.8863, 0.8946 and 0.9158 are all under 0.95, so *the
guardrail was missed* remains true and is if anything understated. **The margin does
not survive.** No sentence should quantify how far under the bar the system sits from
a single 16-question run at this temperature.

Not corrected here: doing so means changing a displayed number, which means changing
the run it is generated from. This file records the finding; acting on it is its own
decision.

## Separate finding, independent of all of the above

`apps/agent/src/dcode_agent/groundedness.py:61-62` returns `score=1.0` when an answer
contains no citations at all. **An answer that cites nothing scores perfectly**, and
q-002 in the post-fix arm went from 3 verified citations to 0 while still scoring
1.000. The metric therefore rewards not citing, which matters more to the guardrail
than anything measured above: an agent that emitted no references would report perfect
groundedness.

Deliberately not fixed. It changes how the score is computed, so it needs its own
decision and its own before/after — the same reason `_verify_symbol`'s exact match was
left disagreeing with `routes/internal.py`'s suffix match.
