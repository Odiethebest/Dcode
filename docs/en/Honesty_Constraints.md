# Honesty Constraints

This document exists because the project's central claim is narrow and easy to
fake: **every citation presented as indexed code evidence is verified before a
user sees it.** Ordinary inline code is formatting, not an implicit citation; a
server-owned evidence ID or explicit `file.py:line` is the claim the guardrail
checks. A system can produce a convincing verified-citations interface without
any verification behind it, and the difference is invisible from a screenshot.
So the rules below are written down, and most are pinned by tests.

Several of them look like things worth cleaning up. They are not. Each entry
gives the rule and the reason, because the reason is what stops a later change
from quietly undoing it.

---

## 1. A turn's state is derived from events, never from time

The agent streams Server-Sent Events. A turn's rendering state is computed purely
from which events have arrived — never from a timer, an optimistic guess, or a
"probably done by now".

| State | Condition | What renders |
|---|---|---|
| `streaming` | stream open, no terminal event | reasoning trace; answer text types in; **no citation chips, no verified marks, no groundedness score** |
| `done` | `final_answer` arrived | chips bind, verified marks set from each event's real flag, pill resolves to `grounded X.XX · N tools` |
| `interrupted` | stream ended **without** `final_answer` | demoted draft, explicitly labelled unverified |
| `error` | `error` event arrived | error state |

There are no verified marks during streaming for a simple reason: those events do
not exist yet. Showing them early would mean inventing them. The trace pill reads
a neutral `reasoning…`, not a premature `grounded 1.00`.

`citation × M` and `final_answer` arrive **together at the end of a run** — the
agent flushes citations after the graph completes. That is the real backend
ordering, not a UI simplification, and the UI reflects it: the verified stamp
appears exactly once, at the moment citations actually arrive. There is no
token-level "verifying → verified" animation anywhere in the product.

> The landing page's hero card *does* animate verifying → verified. That is
> marketing motion on a static mock, explicitly not product state, and it is the
> single exception. The exemption covers the *motion*, not the mock — §12.

### `done` is gated on `final_answer` alone

Not on "the stream closed". This was a real defect: `closed` was treated as
settled, so a turn cut short — by pressing Stop, or by a dropped connection —
rendered its unredacted draft in the authoritative answer voice, bound citation
chips to it, and left the progress pill spinning forever.

Because every downstream check reads `state === 'done'`, keeping `interrupted` a
separate state is what keeps chips, sources, and groundedness off an interrupted
turn without special-casing each one.

## 2. `final_answer.answer` is the authoritative text

Not the concatenation of the streamed `partial_answer` deltas. The groundedness
guardrail may have **redacted** unverifiable references from the draft, so the
settled text has to be the post-redaction version.

This means the settled answer can legitimately differ from what you just watched
stream in. That is the guardrail working, not a flicker bug. Do not "fix" it by
preferring the streamed text.

## 3. An interrupted turn is shown, but never as an answer

The draft is kept — someone who pressed Stop usually did it to read what was
there — and demoted so it cannot be mistaken for a result: muted prose, a neutral
rule down the side, a `Draft · never verified` label, and a plain-language line
saying it was never checked against the index.

Three specifics matter:

- **Every reference inside stays inert**, even when citation events had already
  arrived before the abort. Citations flush just before `final_answer`, so that
  window is real: those citations may each be individually verified while the
  *text around them* was never redacted. Binding them would stamp a guarantee the
  turn never earned.
- **It never enters conversation history.** An unredacted draft fed back as
  context could reintroduce references that failed verification.
- **The progress indicator is static.** A pulsing indicator on a stopped stream
  implies work still happening.

Interrupting stays possible on purpose — real-model runs are slow and the agent
sometimes goes down the wrong path — but only deliberately, via an explicit Stop
button. Submitting a new question while one is streaming is blocked, because
implicit abort-by-submitting is what produced the defect above.

## 4. Three kinds of reference, kept distinct

Matching is keyed on `symbol | file_path | line`.

| Case | Renders as | Why |
|---|---|---|
| prose reference **with** a matching citation event | clickable chip, verified per the event, opens the inspector | it is a real verified citation |
| prose reference with **no** event | **inert** code token — not clickable, no verified implication | with no event there is no "we checked and it failed" signal |
| citation event with **no** prose match | listed in a per-turn **Sources** footer, clickable | never silently drop a verified citation |

The middle row is the subtle one. It would be tidier to render it as an
"unverified" chip, and that would be wrong: **unverified** means *checked, and it
failed*. **No record** means *never checked*. Collapsing them would let the UI
claim a verification attempt that never happened. Preserving the distinction is
the point, not an oversight.

Net guarantees: a reference can never look clickable and do nothing, and a
verified citation can never vanish.

## 5. Verified, unverified, and indexed are three different marks

- **verified** (green, check) — this citation passed the groundedness check.
- **unverified** (amber, hollow) — this citation was checked and failed. Rendered
  honestly, never green-checked.
- **indexed** (neutral grey, list glyph) — this symbol was reached by walking the
  call graph. It came out of the index, but it never went through groundedness.

The third exists because the inspector lets you walk from a citation to its
callers and callees. Those nodes are real, but stamping them `verified` would
claim a check that never ran, and leaving them blank reads as untrustworthy.
`indexed` says exactly what is known and nothing more. It sits deliberately
outside the good/warning colour language so it cannot be read as a verdict.

Solid, filled emphasis is reserved for verified and active states. An earlier
build shipped a filled unverified chip, which made an unverified reference read as
*more* emphasised — and so more trustworthy — than a verified one. A test pins
"unverified is never solid".

## 6. Groundedness is deliberately measured before redaction

The score is the fraction of the model's citations that passed verification **in
the draft**, not in the delivered answer.

An answer with no citations scores `0.0`, not `1.0` and not “excluded”. Excluding
it would let an uncertain agent improve its own denominator by citing nothing;
scoring it perfectly would reward the same failure directly. The evaluation
output therefore reports `answers_without_citations` alongside the mean so
“cited nothing” remains distinguishable from “all cited claims failed”.

The obvious change here is a trap, so it is worth being explicit. Unverifiable
references are already stripped before the user sees the answer. If the score
counted only what survived, it would be scoring a set that is verified *by
construction*, groundedness would sit at ≈1.0 trivially, B4's composite would
inflate, and the H1 verdict could flip for a purely cosmetic reason. That is
p-hacking in the costume of a bug fix.

Measured before redaction, the number answers a real question: **how clean was
the model's draft?** A heavily-redacted answer scores low, which is correct — the
user got safe output, but the model needed a lot of correcting to produce it.

The consequence is that this guardrail can visibly fail. On the recorded run B4
scores 0.916 against a pre-registered floor of 0.95, and that is reported as a
failure rather than explained away. Tightening the synthesis prompt so the model
cites only server-owned evidence IDs is a legitimate class of fix — it changes
the system, not the metric — and it has to be reported as its own change. The
recorded three-arm experiment also showed why merely withdrawing valid symbol
tokens was not sufficient: the durable remedy was one shared symbol-resolution
rule. The implementation later moved to server-owned evidence IDs as a further
contract hardening step; that newer path has not received a complete H1 re-run.

## 7. Markdown is rendered, never injected

Answers render through a markdown-to-React-element pipeline with no
`dangerouslySetInnerHTML` and no raw-HTML plugin. Embedded HTML in model output is
ignored, not executed. XSS-safe by construction rather than by sanitising.

Math is parsed only from Markdown math nodes and rendered with KaTeX. The
frontend normalizes `\(...\)` and `\[...\]` to the Markdown delimiters understood
by `remark-math`, but skips inline code and fenced code blocks so a code example
cannot be reinterpreted as a formula. The synthesis prompt prefers `$...$` and
`$$...$$`; normalization is a compatibility boundary, not permission to inject
raw HTML.

## 8. Source and graph lookups degrade, never fabricate

Clicking a citation fetches real indexed source and highlights the cited line.
When the exact line is not inside an indexed chunk, resolution falls back in
order: the chunk containing the line → the symbol's own chunk → a file outline →
an honest "not indexed at this granularity". It never returns a 500 and never
returns invented source.

Both design prototypes in `design/` mock the stream, the groundedness score, the
source, and the graph edges. The shipped UI is driven by real endpoints only.
Where an endpoint was missing, a thin real one was added — the inspector's source
and neighbours routes exist for exactly this reason.

## 9. Cached state is not presented as current

When a status request fails, the UI says so rather than falling back to the last
value as though it were live. The repo switcher shows `status unavailable` when
the gateway is unreachable, and labels repositories it is not actively polling as
`last known · <status>`.

Stale data displayed confidently is the same failure as an invented number, and
harder to notice.

## 10. An incomplete index says so

The indexer skips files that are too large or fail to parse, which makes the
index incomplete — and therefore makes answers built on it incomplete. The
switcher shows the skipped count on its **closed** state, not only inside a
dropdown, and leads with the consequence: *these aren't in the index, so no answer
can cite them.* A silently partial index lets someone trust a confidently
incomplete answer.

The same applies to a failed index: show the reason, not just that it failed.

## 11. Displayed numbers are generated, never transcribed

Every official H1 snapshot figure in the UI and in the generated documentation
blocks comes from `results/eval-real/` through
`scripts/sync_eval_artifacts.py`, and `make check` fails if any of those surfaces
drifts. A separately labelled experiment report may contain figures derived
from its own committed run directories; it must name that authority explicitly
and must not imply that the generated-artifact drift check covers it.

This rule was earned. The same defect occurred three times: numbers hand-copied
into a surface, then reality moved and the copy stayed. It hit the frontend's
evaluation snapshot (figures from a run that was never archived), the landing
page's baseline chart (decorative hardcoded bars showing the system winning while
the methodology page reported the hypothesis unsupported), and the README plus
this document set (stub-run numbers left in place after the real-model run).

Prose around the official snapshot is not generated, so it carries qualitative
conclusions only — *H1 unsupported*, *the archived sparse baseline was not
BM25*, *the graph's contribution is unmeasured*. Any specific official-snapshot
figure belongs inside a generated block. Experimental figures belong in their
named experiment record; when a report cites one, it must state that exception
and link the authority.

### The generator is a pure function of committed bytes

The generator may only read bytes under `results/<run>/`. Any input taken from
filesystem metadata, the wall clock, or a constant in the source is a bug —
"the numbers come from the results directory" is only true while the generator
is a pure function of those bytes.

This is also the limit of what `make check` is worth. `--check` proves that
every displayed figure agrees with the generator's own inputs; it does not
prove those inputs are true. A generator reading the wrong source is green.
That class of defect cannot be caught downstream — it is only excluded
structurally, by the rule above.

This was earned too. The recorded date was derived from `h1_report.json`'s
mtime, which git does not preserve, so the drift check was anchored to a value
no two checkouts agree on: the gate went red a day after the run and stayed red,
and "fixing" it by regenerating would have stamped the checkout date into the
artifacts as though it were the run's. A gate that is permanently red gets
routed around, and this one is the only thing holding the rule above in place.

Metadata for an **archived** run may be a pinned literal, but it must live in a
separate file from the harness's own output, and it must say **recovered**
rather than **recorded**. The test is whether the copied value can still change,
not whether it was typed by hand: a finished run's date will never move again,
so pinning it is safe by construction, while a model name that a future run will
choose differently is not. Keeping it out of `run_config.json` is what stops a
hand-reconstructed value from reading as something the harness observed.

## 12. A mock must be identifiable as a mock

The exemption in §1 licenses the *motion*, not the mock. It establishes that the
hero's verifying → verified sequence is theatre. It says nothing about whether
the card that theatre plays on can be recognised as one.

So: any surface showing a metric-shaped figure is either driven by a real source
or identifiable as an illustration. **An artefact indistinguishable from a
measurement is an over-claim, even when every individual statement on it is
true.**

The hero card is the case that produced this rule, and it produced it by being
clean. The citation coordinates on it are real locations in the indexed corpus.
The mock answer is plausible. `1.00` was the arithmetically correct score for its
own two verified mock citations. Nothing was fabricated and no number was
transcribed — so rule 11 had nothing to say, and neither did *never fabricate
data*. And yet the card was indistinguishable from a screenshot of a real answer,
and the first groundedness figure a visitor met on that page was a perfect one,
two screens above the recorded value, which is under the bar.

Every other rule here governs whether the interface says something false. This
one governs whether it lets someone believe they are looking at a measurement.
That is a different failure and it needs its own rule.

The label is also subject to the pattern this document keeps recording: it may
not be the smallest or faintest thing on the surface it qualifies. A disclosure
demoted to fine print is the same defect as no disclosure, arrived at politely.

## 13. Chinese and English answers follow the current question

For the supported bilingual contract, the current user question owns the answer
language. A Chinese question receives Chinese prose and an English question
receives English prose; source comments, code identifiers, retrieved evidence,
and earlier turns do not override it. Code identifiers and citation tokens stay
verbatim in either language.

The deterministic selector treats the presence of a Han character as Chinese
and otherwise defaults to English, which keeps Latin-heavy code symbols from
misclassifying a Chinese question. This is deliberately a Chinese/English
contract, not a claim of general language detection. Follow-up
contextualization preserves that selected language rather than translating the
question.

---

## Where these are enforced

UI rules are pinned by tests in `apps/frontend/tests/` — an interrupted turn
never renders as settled and never binds chips; an unverified chip is never
solid; a walked graph node is marked indexed rather than verified; math
delimiter normalization skips code; the landing chart's bars trace to the
snapshot and none is full-width; the methodology page names the leading
baseline from the data rather than from a hardcoded string. Agent tests pin the
Chinese/English selector, history contextualization, server-owned evidence IDs,
zero-citation score, and exact-token redaction.

The intent is that breaking one of these rules breaks a test with a comment
explaining why the rule exists.
