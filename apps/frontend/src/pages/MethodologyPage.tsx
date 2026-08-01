import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { buttonClasses } from '@/components/ui';
import {
  baselineLabels,
  demoCases,
  h1Report,
  levelSummary,
  snapshotSource,
  suiteSummary,
  type BaselineName,
  type Level,
  type Taxonomy,
} from '@/demo/evalSnapshot';
import { RUN_GROUNDEDNESS_BAR } from '@/demo/runGuardrail';
import { cx } from '@/lib/cx';

const BASELINE_ORDER: BaselineName[] = ['B1', 'B2', 'B3', 'B4'];
const TAXONOMY_ORDER: Taxonomy[] = ['L2', 'L3'];
const LEVEL_ORDER: Level[] = ['L1', 'L2', 'L3'];

const LEVEL_LABELS: Record<Level, string> = {
  L1: 'single-hop',
  L2: 'cross-file',
  L3: 'architecture',
};

/**
 * The rung that actually leads the suite on retrieval, read from the data.
 *
 * Exported so a test can feed it a ladder where a different arm wins. Asserting
 * only against the current snapshot cannot tell this apart from a hardcoded
 * `'B4'` — that would pass for exactly as long as B4 happens to lead, and the
 * highlight would then point at the wrong row in the run that changes it.
 *
 * Ties keep the earlier rung, matching the landing page's ladder.
 */
export function leadingBaselineByNdcg(
  summary: Record<BaselineName, { ndcgAtK: number }>,
  order: BaselineName[] = BASELINE_ORDER
): BaselineName {
  return order.reduce((best, b) => (summary[b].ndcgAtK > summary[best].ndcgAtK ? b : best));
}

const retrievalLeader = leadingBaselineByNdcg(suiteSummary);

/**
 * Repeat spread, derived — never typed.
 *
 * This replaced a hand-written paragraph claiming the verdict hinged on B2/B3
 * being scored by a different rule than B4. That was true under the `v1`
 * protocol and stopped being true when every agent arm moved to one rule, but
 * the sentence stayed on the page because prose is not covered by the drift
 * check. The fact that actually makes this verdict fragile is measured and
 * lives in the snapshot, so the page reads it instead of asserting it.
 */
const l2RepeatMargins = h1Report.perRepeat.map((r) => r.marginVsB3.L2);
const supportedRepeats = h1Report.perRepeat.filter((r) => r.decision === 'supported').length;
const l2MarginSpread = Math.max(...l2RepeatMargins) - Math.min(...l2RepeatMargins);

/** Signed, fixed-precision — positive margins get an explicit +. */
function signed(n: number, digits = 3): string {
  const s = n.toFixed(digits);
  return n >= 0 ? `+${s}` : s;
}

/** A margin is good if it clears the pre-registered bar, bad if negative,
 *  warn if positive but short of the bar. */
function marginTone(m: number): Tone {
  if (m >= h1Report.threshold) return 'good';
  if (m < 0) return 'bad';
  return 'warn';
}

export default function MethodologyPage() {
  const [taxonomy, setTaxonomy] = useState<Taxonomy>('L2');
  const visibleCases = useMemo(() => demoCases.filter((c) => c.taxonomy === taxonomy), [taxonomy]);
  const [selectedQuestionId, setSelectedQuestionId] = useState(visibleCases[0]?.questionId ?? '');

  useEffect(() => {
    if (!visibleCases.some((c) => c.questionId === selectedQuestionId)) {
      setSelectedQuestionId(visibleCases[0]?.questionId ?? '');
    }
  }, [selectedQuestionId, visibleCases]);

  const selectedCase =
    visibleCases.find((c) => c.questionId === selectedQuestionId) ?? visibleCases[0];
  const questionCount = suiteSummary.B4.questions;

  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* header */}
      <header className="sticky top-0 z-40 border-b border-line bg-[color-mix(in_srgb,var(--paper)_84%,transparent)] backdrop-blur-md">
        <div className="mx-auto flex h-[70px] max-w-content items-center gap-6 px-8 max-[600px]:px-5">
          <Link
            to="/"
            className="flex items-baseline gap-2 font-display text-2xl font-semibold tracking-tight"
          >
            Dcode
            <span
              className="h-[7px] w-[7px] -translate-y-0.5 rounded-full bg-brand"
              aria-hidden="true"
            />
          </Link>
          <span className="font-mono text-[12px] uppercase tracking-[0.16em] text-ink-3 max-[600px]:hidden">
            Methodology
          </span>
          <div className="flex-1" />
          <Link className={buttonClasses('primary', 'md')} to="/workbench">
            Open the demo <span className="font-mono text-xs opacity-70">→</span>
          </Link>
        </div>
      </header>

      {/* hero */}
      <section className="mx-auto max-w-content px-8 pb-16 pt-[72px] max-[600px]:px-5 max-[600px]:pt-12">
        <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-ink-3">
          The evidence
        </div>
        <h1 className="my-5 max-w-[18ch] font-display text-[clamp(38px,5.6vw,64px)] font-medium leading-[1.03] tracking-[-0.022em]">
          We tried to prove ourselves <em className="italic text-brand">wrong.</em>
        </h1>
        <p className="max-w-[62ch] font-display text-[clamp(17px,2vw,21px)] leading-[1.5] text-ink-2">
          Dcode ships a falsifiable claim and a scoreboard, not a demo reel. The hypothesis, the bar
          it has to clear, and the current result are all below — read straight from{' '}
          <Mono>{snapshotSource.path}</Mono>, a full real-model run over {questionCount} questions
          whose verdict was written {snapshotSource.verdictWritten} — provenance metadata, not a
          timestamp the harness recorded. Every figure on this page is copied from a file in that
          directory, and the directory is in the repository.
        </p>
        <div
          className={cx(
            'mt-7 inline-flex items-center gap-2.5 rounded-full border px-4 py-2',
            h1Report.decision === 'supported'
              ? 'border-good bg-good-wash'
              : 'border-warn bg-warn-wash'
          )}
        >
          <span
            className={cx(
              'h-2 w-2 rounded-full',
              h1Report.decision === 'supported' ? 'bg-good' : 'bg-warn'
            )}
          />
          <span
            className={cx(
              'font-mono text-[13px] font-medium',
              h1Report.decision === 'supported' ? 'text-good' : 'text-warn'
            )}
          >
            H1 — currently {h1Report.decision}
          </span>
        </div>
      </section>

      {/* the claim */}
      <Section
        eyebrow="The claim"
        title={
          <>
            A hypothesis you can <em className="italic text-brand">falsify.</em>
          </>
        }
      >
        <div className="grid grid-cols-[1.1fr_0.9fr] gap-6 max-[920px]:grid-cols-1">
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-brand">
              H1
            </div>
            <p className="font-display text-[clamp(18px,2.2vw,23px)] leading-[1.5] text-ink">
              Structure-aware retrieval — a real call graph and hybrid search, driven by an agent (
              <Mono>B4</Mono>) — answers cross-file questions better than flat dense RAG (
              <Mono>B2</Mono>) and classic hybrid retrieval (<Mono>B3</Mono>).
            </p>
          </div>
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-3">
              The bar (pre-registered)
            </div>
            <p className="text-[14.5px] leading-relaxed text-ink-2">{h1Report.note}</p>
            <p className="mt-4 border-l-2 border-brand pl-4 text-[13.5px] leading-relaxed text-ink-2">
              Thresholds were fixed <b className="font-semibold text-ink">before</b> the numbers
              came in and don&rsquo;t move afterward. If <Mono>B4</Mono> doesn&rsquo;t clear the
              bar, the result is recorded{' '}
              <b className="font-semibold text-ink">{h1Report.decision}</b> — not quietly dropped.
            </p>
          </div>
        </div>
      </Section>

      {/* the verdict */}
      <Section
        eyebrow="The verdict"
        title={
          <>
            Three of four comparisons clear. <em className="italic text-brand">H1 needs four.</em>
          </>
        }
        lede={
          <>
            Composite margin of <Mono>B4</Mono> over each baseline, per question level. Positive
            means B4 is ahead; the bar is <Mono>+{h1Report.threshold.toFixed(2)}</Mono> over{' '}
            <em>both</em> B2 and B3, on <em>both</em> levels. Architecture questions clear against
            both rivals — by {(h1Report.comparisons.L3.marginVsB3 / h1Report.threshold).toFixed(1)}×
            and {(h1Report.comparisons.L3.marginVsB2 / h1Report.threshold).toFixed(1)}× the bar.
            Cross-file clears against dense RAG and falls{' '}
            {(h1Report.threshold - h1Report.comparisons.L2.marginVsB3).toFixed(3)} short against
            hybrid+rerank. H1 is a conjunction, so three of four is{' '}
            <Mono>{h1Report.decision}</Mono>.
          </>
        }
      >
        <div className="grid grid-cols-2 gap-5 max-[760px]:grid-cols-1">
          {TAXONOMY_ORDER.map((level) => {
            const c = h1Report.comparisons[level];
            return (
              <div key={level} className="rounded-card border border-line bg-surface p-6">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-display text-[22px] font-medium">
                    {level} · {LEVEL_LABELS[level]}
                    <span className="ml-2 font-mono text-[12px] text-ink-3">n={c.questions}</span>
                  </span>
                  <span
                    className={cx(
                      'flex-none rounded-full border px-3 py-1 font-mono text-[10.5px] font-medium uppercase tracking-[0.08em]',
                      c.supported
                        ? 'border-good bg-good-wash text-good'
                        : 'border-warn bg-warn-wash text-warn'
                    )}
                  >
                    {c.supported ? 'cleared' : 'did not clear'}
                  </span>
                </div>
                <div className="mt-5">
                  <MarginRow label="B2 · Dense RAG composite" value={c.b2Composite.toFixed(3)} />
                  <MarginRow
                    label="B3 · Hybrid + rerank composite"
                    value={c.b3Composite.toFixed(3)}
                  />
                  <MarginRow label="B4 · Dcode composite" value={c.b4Composite.toFixed(3)} />
                  <MarginRow
                    label="margin vs B2"
                    value={signed(c.marginVsB2)}
                    tone={marginTone(c.marginVsB2)}
                  />
                  <MarginRow
                    label="margin vs B3"
                    value={signed(c.marginVsB3)}
                    tone={marginTone(c.marginVsB3)}
                  />
                </div>
                <p className="mt-4 border-t border-line pt-4 font-mono text-[11px] leading-relaxed text-ink-3">
                  bar · both margins ≥ +{h1Report.threshold.toFixed(2)}
                  <br />
                  one question moves this level by up to {(1 / c.questions).toFixed(3)}; a single
                  question&rsquo;s weight only drops below the bar at n&nbsp;&gt;&nbsp;20
                </p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* the scoreboard */}
      <Section
        eyebrow="The scoreboard"
        title="The baseline ladder, measured."
        lede={
          <>
            {questionCount} questions, the same for every rung, scored on standard IR metrics.{' '}
            <Mono>B4</Mono> is Dcode with the call graph and agent; the rungs below strip capability
            away.
          </>
        }
      >
        <div className="overflow-x-auto rounded-card border border-line bg-surface">
          <table className="w-full min-w-[560px] border-collapse text-left">
            <thead>
              <tr className="border-b border-line font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
                <th className="px-5 py-4 font-medium">Baseline</th>
                <th className="px-4 py-4 text-right font-medium">Recall@k</th>
                <th className="px-4 py-4 text-right font-medium">MRR</th>
                <th className="px-4 py-4 text-right font-medium">nDCG@k</th>
                <th className="px-5 py-4 text-right font-medium">Grounded</th>
              </tr>
            </thead>
            <tbody>
              {BASELINE_ORDER.map((b) => {
                const s = suiteSummary[b];
                const top = b === retrievalLeader;
                const dips = s.groundedness < RUN_GROUNDEDNESS_BAR;
                return (
                  <tr
                    key={b}
                    className={cx('border-b border-line last:border-0', top && 'bg-brand-wash')}
                  >
                    <td className="px-5 py-4">
                      <div
                        className={cx(
                          'font-mono text-[13px] font-semibold',
                          top ? 'text-brand' : 'text-ink-2'
                        )}
                      >
                        {b}
                      </div>
                      <div className="font-display text-[15px] text-ink">{baselineLabels[b]}</div>
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">
                      {s.recallAtK.toFixed(3)}
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">
                      {s.mrr.toFixed(3)}
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">
                      {s.ndcgAtK.toFixed(3)}
                    </td>
                    <td
                      className={cx(
                        'px-5 py-4 text-right font-mono text-[14px] tabular-nums',
                        dips ? 'font-semibold text-warn' : 'text-ink'
                      )}
                    >
                      {s.groundedness.toFixed(3)}
                      {dips && (
                        <span className="ml-1.5 text-[10px] uppercase tracking-[0.08em]">
                          below bar
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-4 max-w-[74ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
          Read it straight:{' '}
          <b className="font-semibold text-ink">
            B4 leads retrieval, and B3 and B4 retrieved the same candidates
          </b>{' '}
          — the difference is that B4 is scored on the evidence it ends up citing and B3 on its
          top-5. Every rung clears the {RUN_GROUNDEDNESS_BAR.toFixed(2)} groundedness guardrail, but
          only B3 and B4 are measured against it: B1 and B2 answer from a template whose
          groundedness is the constant 1.000. Since groundedness is one of the four composite terms,
          a quarter of the B2 column is awarded rather than earned.
        </p>

        {/* the per-level ladder from the corrected BM25 rerun */}
        <div className="mt-10">
          <h3 className="font-display text-[22px] font-medium tracking-[-0.01em]">
            The BM25 rerun —{' '}
            <em className="italic text-brand">and what the ladder actually shows.</em>
          </h3>
          <p className="mt-2 max-w-[68ch] text-[14.5px] leading-relaxed text-ink-2">
            This run records the corrected Okapi BM25 path in B1 and in the sparse arm of B3/B4.
            The ladder climbs as designed on cross-file questions now — sparse, then dense, then
            hybrid, then the full system. It did not before: until test code was excluded from
            retrieval, BM25 alone out-recalled hybrid on both H1 levels. One inversion survives and
            is reported rather than smoothed: on architecture questions sparse B1 still edges dense
            B2, by 0.008.
          </p>
          <div className="mt-5 overflow-x-auto rounded-card border border-line bg-surface">
            <table className="w-full min-w-[560px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
                  <th className="px-5 py-4 font-medium">Level · Recall@k</th>
                  {BASELINE_ORDER.map((b) => (
                    <th key={b} className="px-4 py-4 text-right font-medium">
                      {b}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {LEVEL_ORDER.map((level) => (
                  <tr key={level} className="border-b border-line last:border-0">
                    <td className="px-5 py-4">
                      <span className="font-mono text-[13px] font-semibold text-ink-2">
                        {level}
                      </span>{' '}
                      <span className="font-display text-[15px] text-ink">
                        {LEVEL_LABELS[level]}
                      </span>
                      <span className="ml-2 font-mono text-[11px] text-ink-3">
                        n={levelSummary[level].B4.questions}
                      </span>
                    </td>
                    {BASELINE_ORDER.map((b) => (
                      <td
                        key={b}
                        className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink"
                      >
                        {levelSummary[level][b].recallAtK.toFixed(3)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 max-w-[74ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
            Note the L3 row contradicts itself: sparse <Mono>B1</Mono> posts the <em>highest</em> L3
            recall of any rung. On three questions that is almost certainly one lucky lexical hit,
            not evidence that BM25 understands architecture. It is left in because deleting
            inconvenient rows is how scoreboards start lying.
          </p>
        </div>
      </Section>

      {/* why the verdict reads the way it does */}
      <Section
        eyebrow="The diagnosis"
        title={
          <>
            The graph is now measured — and it is{' '}
            <em className="italic text-brand">small</em>.
          </>
        }
        lede="B4 clears a level outright. Most of that margin is not the call graph, and the margin that decides the rest is smaller than its own run-to-run noise."
      >
        <div className="grid grid-cols-[1.15fr_0.85fr] gap-6 max-[920px]:grid-cols-1">
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <p className="text-[15px] leading-relaxed text-ink-2">
              <b className="font-semibold text-ink">
                The call graph&rsquo;s own contribution is positive, consistent across both levels,
                and small.
              </b>{' '}
              It was negative two runs ago, before graph results carried their source code into the
              answer prompt. Every citation records the tool that surfaced it, so evidence the graph
              found that hybrid retrieval had not already returned is counted rather than assumed —
              per question in <Mono>new_gt_hits_from_graph_evidence</Mono>, and at the level of the
              decision by the ablation below. The margins are in{' '}
              <Mono>h1_report.json</Mono> under <Mono>diagnostics</Mono>.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-2">
              And it is not what is doing the work. The <Mono>B3.5</Mono> arm is B4 with the graph
              and reference tools switched off and everything else identical, so the two halves come
              apart: on architecture questions{' '}
              <b className="font-semibold text-ink">
                the agent&rsquo;s multi-step evidence gathering is worth several times the graph
              </b>
              . Without that ablation all of it would have been reported as the graph&rsquo;s.
            </p>
            <p className="mt-4 border-l-2 border-brand pl-4 text-[14px] leading-relaxed text-ink-2">
              The verdict is fragile for a different reason: across{' '}
              {h1Report.repeats} identical repeats the deciding{' '}
              <Mono>L2</Mono> margin ranged over {l2MarginSpread.toFixed(3)}, wider than the{' '}
              {h1Report.threshold.toFixed(2)} bar it is compared against, and{' '}
              <b className="font-semibold text-ink">
                {supportedRepeats} of {h1Report.repeats} repeats returned{' '}
                <Mono>supported</Mono> on its own
              </b>
              . The reported decision is the mean of all {h1Report.repeats}; each repeat keeps its
              own verdict in <Mono>h1_report.json</Mono>. A single run of this suite cannot separate
              an effect this size from which way the model happened to phrase an answer.
            </p>
          </div>
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-3">
              What would re-open it
            </div>
            <ol className="space-y-3.5 text-[14px] leading-relaxed text-ink-2">
              <li>
                <b className="font-semibold text-ink">One scoring rule for every arm.</b> Today
                B2/B3 are scored on retrieved top-k and B4 on verified final evidence. That
                difference is worth more than the margin L3 missed by, so nothing can be concluded
                until it is fixed — before the run, not after.
              </li>
              <li>
                <b className="font-semibold text-ink">A dense-only agent mode for B2.</b> B1 and B2
                answer from a template, so their groundedness is the constant 1.000 — a quarter of a
                composite, awarded rather than measured. Until B2 shares the synthesis path, no
                symmetric rule can include it.
              </li>
              <li>
                <b className="font-semibold text-ink">A B3.5 ablation</b> — same agent, call-graph
                tools disabled. B4 − B3 measures the whole agent; B4 − B3.5 measures the graph
                alone, which is the actual hypothesis. Diagnostic only: adding an arm to the pass
                criteria would be changing the pass criteria.
              </li>
            </ol>
            <p className="mt-5 border-t border-line pt-4 font-mono text-[11px] leading-relaxed text-ink-3">
              The previous re-open criteria were met and run — that is this result. One of them
              carried a prediction that the data falsified: scoring B4 on its smaller evidence set
              was pre-registered as a handicap, and it turned out to be an advantage.
            </p>
          </div>
        </div>
      </Section>

      {/* integrity */}
      <Section
        eyebrow="The rules"
        title="What we don't get to change."
        lede="A pre-registered threshold only means something if it can fail. This one did."
      >
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-card border border-line bg-line max-[920px]:grid-cols-1">
          <Rule
            title="Fixed before, untouched after"
            body="Thresholds, the question set, and the metric definitions were locked before the run and have not moved since. The result above is what came out."
          />
          <Rule
            title="Change what's measured, never the bar"
            body="The corrections above change which output gets scored — an objective gap in the harness. The pass criteria stay exactly where they were."
          />
          <Rule
            title="Either outcome gets published"
            body="If corrected scoring clears the bar, that's a win earned by measuring the right thing. If it doesn't, it's recorded unsupported. This page shows whichever happened."
          />
        </div>
      </Section>

      {/* the transcripts */}
      {/* Titled "Every question, every baseline." while rendering four of the
          sixteen. The honest scope was already in the footnote below — the
          prominent line was the flattering one, which is the shape this page
          keeps having to correct. Both counts are read from the generated
          snapshot, so changing the demo set or the suite can never strand a
          hand-typed number in this heading. */}
      <Section
        eyebrow="The transcripts"
        title={
          <>
            {demoCases.length} of {questionCount} questions, every baseline.
          </>
        }
        lede="The exact answers and citations each baseline produced on the same snapshot. Nothing here is regenerated live."
      >
        <div className="flex gap-2">
          {TAXONOMY_ORDER.map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => setTaxonomy(level)}
              aria-pressed={taxonomy === level}
              className={cx(
                'rounded-[9px] px-4 py-2 font-mono text-[13px] font-medium transition',
                taxonomy === level
                  ? 'bg-brand text-white'
                  : 'border border-line-2 text-ink-2 hover:bg-sunk'
              )}
            >
              {level}
            </button>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-[300px_minmax(0,1fr)] gap-6 max-[920px]:grid-cols-1">
          <aside className="space-y-2">
            {visibleCases.map((c) => {
              const active = c.questionId === selectedCase?.questionId;
              return (
                <button
                  key={c.questionId}
                  type="button"
                  onClick={() => setSelectedQuestionId(c.questionId)}
                  className={cx(
                    'block w-full rounded-card border p-4 text-left transition',
                    active
                      ? 'border-brand bg-brand-wash'
                      : 'border-line bg-surface hover:border-line-2'
                  )}
                >
                  <div className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
                    {c.questionId}
                  </div>
                  <div className="mt-1.5 font-display text-[15px] leading-snug text-ink">
                    {c.question}
                  </div>
                </button>
              );
            })}
          </aside>

          {selectedCase && (
            <div className="space-y-5">
              <div className="rounded-card border border-line bg-surface p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="font-display text-[20px] font-medium leading-snug text-ink">
                    {selectedCase.question}
                  </h3>
                  <span className="rounded-md bg-sunk px-2.5 py-1 font-mono text-[11px] text-ink-2">
                    {selectedCase.taxonomy}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[12px] text-ink-3">
                  ground truth:
                  {selectedCase.gtFiles.map((f) => (
                    <span key={f} className="rounded-[5px] bg-good-wash px-1.5 py-px text-good">
                      {f}
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 max-[600px]:grid-cols-1">
                {BASELINE_ORDER.map((b) => {
                  const a = selectedCase.baselines[b];
                  const grounded = a.groundedness >= RUN_GROUNDEDNESS_BAR;
                  return (
                    <div key={b} className="rounded-card border border-line bg-surface p-5">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-display text-[16px] font-medium text-ink">
                          {b}{' '}
                          <span className="font-mono text-[12px] text-ink-3">
                            · {baselineLabels[b]}
                          </span>
                        </span>
                        <span
                          className={cx(
                            'rounded-full border px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.06em]',
                            grounded
                              ? 'border-good bg-good-wash text-good'
                              : 'border-warn bg-warn-wash text-warn'
                          )}
                        >
                          grounded {a.groundedness.toFixed(3)}
                        </span>
                      </div>

                      <div className="mt-3 grid grid-cols-3 gap-2">
                        <Metric label="Recall@k" value={a.recallAtK.toFixed(3)} />
                        <Metric label="MRR" value={a.mrr.toFixed(3)} />
                        <Metric label="nDCG@k" value={a.ndcgAtK.toFixed(3)} />
                      </div>

                      <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-[10px] bg-sunk-2 px-3.5 py-3 font-mono text-[11.5px] leading-relaxed text-ink-2">
                        {a.answer}
                      </pre>

                      {a.citations.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {a.citations.map((cite, i) => (
                            <span
                              key={`${b}-${i}-${cite}`}
                              className="rounded-[5px] border border-line bg-paper px-1.5 py-px font-mono text-[11px] text-ink"
                            >
                              {cite.replace(/`/g, '')}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </Section>

      {/* honest footnote */}
      <section className="border-t border-line py-14">
        <div className="mx-auto max-w-content px-8 max-[600px]:px-5">
          <p className="max-w-[74ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
            Scope, plainly: {questionCount} questions on the {snapshotSource.corpus} corpus at k=
            {snapshotSource.k}, embedded with {snapshotSource.embedding}, reranked with{' '}
            {snapshotSource.reranker}, answers synthesised by {snapshotSource.synthesis}. One
            repository, one run, verdict written {snapshotSource.verdictWritten} (recovered, not
            recorded) — not a live or large-scale benchmark, and deliberately small enough to stay
            reproducible. Every number on this page is generated from{' '}
            <Mono>{snapshotSource.path}</Mono>, which is committed alongside this code; if a figure
            here disagrees with that directory, the directory is right.
          </p>
          <p className="mt-4 max-w-[74ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
            <b className="font-semibold text-ink">B0</b> (external code search) is absent from the
            ladder rather than scored zero: it needs an API token this run didn&rsquo;t have, so it
            is <em>not measured</em>. It has no bearing on the H1 verdict, which rests on B2, B3 and
            B4.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link className={buttonClasses('primary', 'lg')} to="/workbench">
              Try it on your own repo <span className="font-mono text-xs opacity-70">→</span>
            </Link>
            <Link className={buttonClasses('ghost', 'lg')} to="/">
              Back to the overview
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

type Tone = 'neutral' | 'good' | 'warn' | 'bad';

function MarginRow({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: Tone;
}) {
  const toneClass: Record<Tone, string> = {
    neutral: 'text-ink',
    good: 'text-good',
    warn: 'text-warn',
    bad: 'text-bad',
  };
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[14px] text-ink-2">{label}</span>
      <span className={cx('font-mono text-[15px] font-semibold tabular-nums', toneClass[tone])}>
        {value}
      </span>
    </div>
  );
}

function Rule({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-surface p-[26px]">
      <h3 className="mb-2.5 font-display text-[19px] font-medium tracking-[-0.01em]">{title}</h3>
      <p className="text-[14px] leading-relaxed text-ink-2">{body}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[8px] bg-sunk px-2.5 py-2">
      <div className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-ink-3">{label}</div>
      <div className="mt-0.5 font-mono text-[13px] font-semibold tabular-nums text-ink">
        {value}
      </div>
    </div>
  );
}

function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono text-[0.9em] text-ink">{children}</span>;
}

function Section({
  eyebrow,
  title,
  lede,
  children,
}: {
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-line py-16 max-[600px]:py-12">
      <div className="mx-auto max-w-content px-8 max-[600px]:px-5">
        <div className="mb-9 max-w-[60ch]">
          <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-ink-3">
            {eyebrow}
          </div>
          <h2 className="mt-3 font-display text-[clamp(26px,3.6vw,40px)] font-medium leading-[1.08] tracking-[-0.02em]">
            {title}
          </h2>
          {lede && (
            <p className="mt-4 max-w-[58ch] font-display text-[clamp(16px,1.8vw,19px)] leading-[1.5] text-ink-2">
              {lede}
            </p>
          )}
        </div>
        {children}
      </div>
    </section>
  );
}
