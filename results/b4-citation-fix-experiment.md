# B4 citation handling — three arms, nine runs, 2026-07-30

**Read the last section first.** This file grew as the experiment did, and its
conclusion reverses the change it was opened to measure: `da2b6bc` treated the wrong
end of the defect, and the remedy that survives is `029b9de`. The earlier sections are
kept in the order they were written, with their corrections attached, because the route
to that conclusion is the part worth reading — two mutually concealing errors held it up
for a full round.

**No run here is a verdict.** All nine are single-baseline B4 runs, which carry no H1
decision. `results/eval-real/` remains the recorded H1 result and is untouched in every
figure.

| Arm | symbol tokens offered | guardrail's symbol rule | runs |
|---|---|---|---|
| **original** | yes | exact match only | 3 |
| **A** = `da2b6bc` | no | exact match only | 3 |
| **B** = `029b9de` | yes | shared rule (exact, then dotted suffix) | 3 |

## Why a control run exists at all

The first instinct was to compare the post-fix run against `results/eval-real/`'s
`0.9158`. That comparison is invalid, and finding out why is the main result of this
file: the archived figure is a **single sample taken on another day from a process
that recorded none of its conditions**, and answer synthesis runs at
`temperature=0.1`, not `0`. So a second run of the *unchanged* code was needed to
learn what a repeat costs before any difference could be attributed to the change.

## Design

Every arm in one session, against one live stack, differing only in the agent image
(written when there were two arms; a third was added later under the same conditions):

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
a source edit does not reach the agent until it is rebuilt; every arm was confirmed
inside the container before its run started — the allowed-list branch present or absent,
the prompt rule present or absent, and for arm B also `candidate_filter` in the
guardrail and the shared import in the api container.

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

## Three runs per arm — appended 2026-07-30

The two runs above could not separate the change from noise, so each arm was taken to
n=3 in the same session. Criteria were fixed before the numbers were seen: effect
judged against the pooled standard deviation, and the H1 gap judged in units of the
margin's own standard deviation.

| Arm | groundedness (3 runs) | mean | s | L2 margin vs B3 | s | L3 margin vs B3 | s |
|---|---|---:|---:|---:|---:|---:|---:|
| pre-fix | 0.8863 · 0.8376 · 0.8776 | 0.8672 | 0.0260 | −0.0365 | 0.0122 | −0.0798 | 0.0067 |
| post-fix | 0.8946 · 0.8914 · 0.8827 | 0.8896 | **0.0061** | −0.0280 | 0.0036 | −0.0726 | 0.0178 |

> **Scored under a convention that has since been corrected.** An answer citing nothing
> scored `1.0`; it now scores `0.0` (`dcode_agent.groundedness.verify`). Read
> *Correction, 2026-07-30* below before using any figure in this table — **two of the
> three conclusions first drawn from it do not survive it.** The runs are kept as taken;
> what changed is how they are scored.

Recall@5, MRR and nDCG@5 were byte-identical in all six runs, and B3's groundedness is
1.000 on every question, so B3's composite is deterministic and the whole margin
distribution comes from B4's synthesis.

### The margin's noise is exactly a quarter of its level's groundedness noise

Predicted from the structure — three of four composite components are deterministic —
and confirmed to four decimals in all four cases:

| | s of that level's groundedness | ÷ 4 | measured margin s |
|---|---:|---:|---:|
| post-fix L2 | 0.0145 | 0.0036 | 0.0036 |
| post-fix L3 | 0.0713 | 0.0178 | 0.0178 |
| pre-fix L2 | 0.0489 | 0.0122 | 0.0122 |
| pre-fix L3 | 0.0267 | 0.0067 | 0.0067 |

The first prediction of this used the *whole-suite* s (0.0061) and came out 2.4× too
low. The mechanism was right and the input was wrong: the margin is computed per level,
so it is that level's groundedness that enters it. **L3's groundedness s is 0.0713
because L3 holds three questions** — the n=3 fragility already recorded in
`Final_Report.md` reappears here as variance rather than as a mean.

### The H1 verdict is not a noise artifact

| Level | mean margin vs B3 | distance to the +0.05 bar | in units of that margin's s |
|---|---:|---:|---:|
| L2 | −0.0280 | 0.0780 | **21.6×** |
| L3 | −0.0726 | 0.1226 | **6.9×** |

Nothing in synthesis variability reaches a gap of 7 to 22 standard deviations.
`unsupported` survives the noise it had never been tested against. For reference, B4
does clear +0.05 against B2 on L2 (+0.1096) and does not on L3 (−0.0169).

### The fix: variance, not mean

The mean moved +0.0224 at a pooled s of 0.0189 — a ratio of 1.19, which on n=3 per arm
is **suggestive and not established**, and the pre-declared threshold for
"indistinguishable" was 1.0. It is not being reported as an improvement in score.

What did move robustly is **spread: s 0.0260 → 0.0061, a 4× reduction**, range 0.0487 →
0.0119. That matches the mechanism exactly — the pre-fix allowed list offered symbol
tokens that always fail verification, and how many the model happened to cite varied
per run, so removing them removed a source of variance rather than a constant penalty.
On n=3 a variance ratio carries little statistical power; the mechanism is what makes it
credible, and it is stated as such.

Caveat kept in view: three samples give a standard deviation with roughly ±40%
uncertainty. These figures separate "the gap is 20× the noise" from "the gap is inside
the noise", which is the resolution the decision needed. They do not support quoting
any of them to three decimals.

### Correction, 2026-07-30 — the two paragraphs above do not survive rescoring

Both claims about the citation fix were artefacts of scoring an uncited answer at
`1.0`. Recomputed on the same six runs under `0.0` — an exact recomputation, not a
re-run, so no new sampling enters:

| | old convention | corrected |
|---|---:|---:|
| pre-fix mean · s | 0.8672 · 0.0260 | **0.8672 · 0.0260** (unchanged — no uncited answers in any of its three runs) |
| post-fix mean · s | 0.8896 · 0.0061 | **0.8479 · 0.0302** |
| effect on the mean | +0.0224 | **−0.0193** — the sign reverses |
| effect on spread | 4× reduction | **none** — 0.0260 → 0.0302, marginally worse |

**The zero-citation branch fired only in the post-fix arm** — once in each of two runs,
never in the three pre-fix runs, and never in `results/eval-real/`. Each firing
collected a free `1.0`.

So the mechanism is the cause of its own measurement artefact: dropping symbol tokens
from the allowed list left the model, on some questions, with nothing it was willing to
cite at all — and the old convention paid a perfect score for exactly that. **The
correction did not merely change a number; it made visible a cost of the fix that the
old convention concealed.**

What still stands, being convention-independent: the redaction count 17 → 10 (a count of
markers in answer text, untouched by scoring), symbol-style citations at zero in every
answer, and the code-and-index argument that the allowed list was offering tokens
`_verify_symbol` rejects by exact match.

What no longer stands: any claim that the fix improved the score or reduced its variance.
Neither is reported. **And the remedy itself is now open to question** — accepting suffix
matches in the verifier (see the separate finding below) would have kept those citations
*and* made them verify, where dropping the tokens removed them. That is a better remedy
on this evidence, and it is the one deliberately not taken here because it moves the
metric upward.

`results/eval-real/` is unaffected in every figure: all four baselines had citations on
all 16 questions, so the branch never executed and the recorded H1 verdict does not move.

### What this does not measure

Under Correction A (criteria set 2, item 1) B4's retrieval metrics would be computed
from its verified citation set, which is LLM output — so all four composite components
become stochastic and the ÷4 relationship above no longer holds. **These runs bound the
margin's noise under the current scoring only, and that bound is a floor, not an
estimate, for what Correction A would produce.**

Deliberately not computed here: what Correction A *would score*. The citation sets are
in these files and the arithmetic is available, but choosing whether to run a
pre-registered correction after seeing what it produces is the contamination the
pre-registration exists to prevent. The decision below is argued from the size of the
gap and from L3's question count, never from a preview of the result.

## The finding that turned out not to be separate — now fixed

`dcode_agent.groundedness.verify` returned `score=1.0` when an answer contained no
citations at all, so **an answer citing nothing scored perfectly** and the metric
rewarded vagueness. It was recorded here as an aside; the recomputation above shows it
was load-bearing for this experiment's own conclusions, which is why the correction sits
in the results rather than in a footnote.

Now `0.0`. The reasoning, and why not "exclude from the average", is in that function's
comment; the short form is that excluding lets an agent drop the questions it is unsure
about out of its own denominator, and `0.0` moves the number against us, which is the
direction to choose in when a convention is being settled after the fact.

`0.0` cannot by itself separate *cited nothing* from *cited ten things, all false* —
which is the collapse Honesty_Constraints §4 forbids for the marks on individual
references. Two things keep them apart: `enforce_groundedness` writes a different
footnote for each, and `dcode_eval.run` reports `answers_without_citations` beside every
groundedness figure. **That count is a condition of this convention, not an
embellishment on it** — a baseline scoring low honestly and one scoring low uselessly
are indistinguishable in the mean alone.

~~Still open~~ **— now fixed too, and it turned out to be the actual defect.** See the
final section. What follows below was written while it was still open; the reason it was
left for later stands, and it was honoured: the change was pre-declared before any run.

Original wording, kept: `_verify_symbol`'s exact
match disagrees with `routes/internal.py`'s suffix match. Fixing that moves the score
**upward**, which is the direction that needs pre-declaration and a published
before/after; this one moved it downward and closed an exploit, which is why it could be
settled now.

---

## Conclusion — arm B is the remedy, arm A was not

Nine runs, three arms, one session, one index, one pair of model sidecars. Only the
agent image differed, verified inside the container before each arm started. Every
groundedness figure below is on the corrected no-citation convention, so the three
arms are comparable; the original and A arms are exact recomputations of the runs
already recorded above, not re-runs.

| Arm | groundedness ×3 | mean | s | uncited answers | redaction markers | verified citations | answers keeping a symbol citation |
|---|---|---:|---:|---|---|---|---|
| original | 0.8863 · 0.8376 · 0.8776 | 0.8672 | 0.0260 | 0 · 0 · 0 | 17 · 19 · 21 | 54 · 48 · 51 | **0 · 0 · 0** |
| A `da2b6bc` | 0.8321 · 0.8289 · 0.8827 | 0.8479 | 0.0302 | 1 · 1 · 0 | 10 · 14 · 12 | 43 · 45 · 47 | 0 · 0 · 0 |
| **B `029b9de`** | 0.9000 · 0.8769 · 0.9040 | **0.8937** | 0.0146 | 0 · 0 · 0 | 12 · 13 · 9 | **65 · 62 · 67** | **2 · 2 · 2** |

Against the criteria fixed before the runs:

| Criterion | Result |
|---|---|
| B vs original — the arms differ *only* in the guardrail's rule | +0.0265, pooled s 0.0211, ratio **1.26** → resolvable |
| B vs A | +0.0457, pooled s 0.0237, ratio **1.93** → resolvable |
| uncited answers in B near zero | **0, 0, 0** |
| redaction markers below the original arm's | **9–13 vs 17–21**, while citing *more* |

**The counts are the evidence; the means are the weak part.** Ratios of 1.26 and 1.93
on n=3 a side are roughly p≈0.25 and p≈0.1 — they clear a threshold declared in advance
and they are not statistical significance, and this file does not describe them as more.
What is not marginal is that **symbol-style citations survived for the first time**: zero
across nine runs of the two exact-match arms, two answers in every run of arm B. Verified
citations rose from 48–54 to 62–67. Those ~13 references were real all along and the
guardrail was deleting them.

B's spread is also the lowest of the three (0.0146). Recorded as an observation only — a
variance ratio on n=3 has almost no power, and a variance claim made on this evidence is
exactly what had to be retracted one section above.

### Why arm A looked best under the old convention and worst under the corrected one

| Arm | old convention | corrected |
|---|---:|---:|
| original | 0.8672 | 0.8672 |
| A | **0.8896** | **0.8479** |
| B | 0.9204 | 0.8937 |

**Two errors were concealing each other for a full round.** Removing the tokens left the
model with nothing to cite on some questions, and scoring an uncited answer at `1.0` paid
a perfect score for exactly that. Under the old convention A therefore read as an
improvement over the original arm; under the corrected one it is the worst of the three.
Neither error was visible while the other was in place, and no single measurement would
have separated them — it took fixing one to make the other legible.

### What this does not change

**H1 remains `unsupported`, and the margins barely moved.**

| Level | B arm margin vs B3 | s | distance to the +0.05 bar |
|---|---:|---:|---:|
| L2 | −0.0253 | 0.0111 | 0.0753 = **6.8× s** |
| L3 | −0.0478 | 0.0235 | 0.0978 = **4.2× s** |

Groundedness rose 0.867 → 0.894 and the L2 margin moved −0.0365 → −0.0253, because
groundedness is one of four equally weighted composite terms. This was stated before the
runs and is repeated because the numbers moved favourably: B4's ceiling under this scoring
is a tie with B3, so no groundedness work can clear a +0.05 bar.

**The final measured arm still missed the 0.95 guardrail**, at 0.894. Under that
protocol, the remaining failures were `file:line` references invented by the
model — a model-behaviour problem rather than a scoring one. The implementation
boundary below limits how that diagnosis can be applied to the current agent.

## Post-experiment implementation boundary

All nine runs above predate `87ffa88`, which replaced model-facing symbol and
location tokens with request-local server-owned evidence IDs such as `[C1]`.
They therefore establish the shared symbol rule under the protocol they
measured, but they do not measure the current citation protocol. In particular,
`0.894` is the last arm-B mean, not an estimate of today's agent, and “invented
`file:line` references are the remaining gap” is the last measured diagnosis
rather than a current-system conclusion.

The later evidence-ID path, exact-token redaction, same-language synthesis, and
multi-turn contextualization are covered by tests and a one-question live smoke.
Only a complete pre-registered B1–B4 run can supersede the recorded H1 result or
establish the current suite-level groundedness.
