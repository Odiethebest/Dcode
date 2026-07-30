import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { buttonClasses } from '@/components/ui';
import {
  demoCases,
  h1Report,
  levelSummary,
  snapshotSource,
  suiteSummary,
  type BaselineName,
  type Level,
  type Taxonomy,
} from '@/demo/evalSnapshot';
import { cx } from '@/lib/cx';

const BASELINE_ORDER: BaselineName[] = ['B1', 'B2', 'B3', 'B4'];
const TAXONOMY_ORDER: Taxonomy[] = ['L2', 'L3'];
const LEVEL_ORDER: Level[] = ['L1', 'L2', 'L3'];

const BASELINE_LABELS: Record<BaselineName, string> = {
  B1: 'BM25 sparse',
  B2: 'Dense RAG',
  B3: 'Hybrid + rerank',
  B4: 'Dcode + graph + agent',
};

const LEVEL_LABELS: Record<Level, string> = {
  L1: 'single-hop',
  L2: 'cross-file',
  L3: 'architecture',
};

/** The rung that actually leads the suite on retrieval, read from the data. */
const retrievalLeader = BASELINE_ORDER.reduce((best, b) =>
  suiteSummary[b].ndcgAtK > suiteSummary[best].ndcgAtK ? b : best
);
const GUARDRAIL = 0.95;

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

  const selectedCase = visibleCases.find((c) => c.questionId === selectedQuestionId) ?? visibleCases[0];
  const questionCount = suiteSummary.B4.questions;

  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* header */}
      <header className="sticky top-0 z-40 border-b border-line bg-[color-mix(in_srgb,var(--paper)_84%,transparent)] backdrop-blur-md">
        <div className="mx-auto flex h-[70px] max-w-content items-center gap-6 px-8 max-[600px]:px-5">
          <Link to="/" className="flex items-baseline gap-2 font-display text-2xl font-semibold tracking-tight">
            Dcode<span className="h-[7px] w-[7px] -translate-y-0.5 rounded-full bg-brand" aria-hidden="true" />
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
        <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-ink-3">The evidence</div>
        <h1 className="my-5 max-w-[18ch] font-display text-[clamp(38px,5.6vw,64px)] font-medium leading-[1.03] tracking-[-0.022em]">
          We tried to prove ourselves <em className="italic text-brand">wrong.</em>
        </h1>
        <p className="max-w-[62ch] font-display text-[clamp(17px,2vw,21px)] leading-[1.5] text-ink-2">
          Dcode ships a falsifiable claim and a scoreboard, not a demo reel. The hypothesis, the bar it has to clear,
          and the current result are all below — read straight from{' '}
          <Mono>{snapshotSource.path}</Mono>, a full real-model run over {questionCount} questions whose verdict was
          written {snapshotSource.verdictWritten} — a recovered date, not one the harness recorded. Every figure on
          this page is copied from a file in that directory, and the directory is in the repository.
        </p>
        <div
          className={cx(
            'mt-7 inline-flex items-center gap-2.5 rounded-full border px-4 py-2',
            h1Report.decision === 'supported' ? 'border-good bg-good-wash' : 'border-warn bg-warn-wash'
          )}
        >
          <span className={cx('h-2 w-2 rounded-full', h1Report.decision === 'supported' ? 'bg-good' : 'bg-warn')} />
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
      <Section eyebrow="The claim" title={<>A hypothesis you can <em className="italic text-brand">falsify.</em></>}>
        <div className="grid grid-cols-[1.1fr_0.9fr] gap-6 max-[920px]:grid-cols-1">
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-brand">H1</div>
            <p className="font-display text-[clamp(18px,2.2vw,23px)] leading-[1.5] text-ink">
              Structure-aware retrieval — a real call graph and hybrid search, driven by an agent (<Mono>B4</Mono>) —
              answers cross-file questions better than flat dense RAG (<Mono>B2</Mono>) and classic hybrid retrieval
              (<Mono>B3</Mono>).
            </p>
          </div>
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-3">The bar (pre-registered)</div>
            <p className="text-[14.5px] leading-relaxed text-ink-2">{h1Report.note}</p>
            <p className="mt-4 border-l-2 border-brand pl-4 text-[13.5px] leading-relaxed text-ink-2">
              Thresholds were fixed <b className="font-semibold text-ink">before</b> the numbers came in and don&rsquo;t
              move afterward. If <Mono>B4</Mono> doesn&rsquo;t clear the bar, the result is recorded{' '}
              <b className="font-semibold text-ink">{h1Report.decision}</b> — not quietly dropped.
            </p>
          </div>
        </div>
      </Section>

      {/* the verdict */}
      <Section
        eyebrow="The verdict"
        title={<>On this snapshot, it <em className="italic text-brand">doesn&rsquo;t clear the bar</em> — yet.</>}
        lede={
          <>
            Composite margin of <Mono>B4</Mono> over each baseline, per question level. Positive means B4 is ahead; the
            bar is <Mono>+{h1Report.threshold.toFixed(2)}</Mono> over <em>both</em> B2 and B3, on <em>both</em> levels.
            B4 clears it against B2 on cross-file questions and against nothing else.
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
                      c.supported ? 'border-good bg-good-wash text-good' : 'border-warn bg-warn-wash text-warn'
                    )}
                  >
                    {c.supported ? 'cleared' : 'did not clear'}
                  </span>
                </div>
                <div className="mt-5">
                  <MarginRow label="B2 · Dense RAG composite" value={c.b2Composite.toFixed(3)} />
                  <MarginRow label="B3 · Hybrid + rerank composite" value={c.b3Composite.toFixed(3)} />
                  <MarginRow label="B4 · Dcode composite" value={c.b4Composite.toFixed(3)} />
                  <MarginRow label="margin vs B2" value={signed(c.marginVsB2)} tone={marginTone(c.marginVsB2)} />
                  <MarginRow label="margin vs B3" value={signed(c.marginVsB3)} tone={marginTone(c.marginVsB3)} />
                </div>
                <p className="mt-4 border-t border-line pt-4 font-mono text-[11px] leading-relaxed text-ink-3">
                  bar · both margins ≥ +{h1Report.threshold.toFixed(2)}
                  {level === 'L3' && (
                    <>
                      <br />
                      n=3 · one question moves the average; significance isn&rsquo;t computable at this size. Don&rsquo;t
                      read L3 in either direction.
                    </>
                  )}
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
            {questionCount} questions, the same for every rung, scored on standard IR metrics. <Mono>B4</Mono> is Dcode
            with the call graph and agent; the rungs below strip capability away.
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
                const dips = s.groundedness < GUARDRAIL;
                return (
                  <tr key={b} className={cx('border-b border-line last:border-0', top && 'bg-brand-wash')}>
                    <td className="px-5 py-4">
                      <div className={cx('font-mono text-[13px] font-semibold', top ? 'text-brand' : 'text-ink-2')}>{b}</div>
                      <div className="font-display text-[15px] text-ink">{BASELINE_LABELS[b]}</div>
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">{s.recallAtK.toFixed(3)}</td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">{s.mrr.toFixed(3)}</td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">{s.ndcgAtK.toFixed(3)}</td>
                    <td
                      className={cx(
                        'px-5 py-4 text-right font-mono text-[14px] tabular-nums',
                        dips ? 'font-semibold text-warn' : 'text-ink'
                      )}
                    >
                      {s.groundedness.toFixed(3)}
                      {dips && <span className="ml-1.5 text-[10px] uppercase tracking-[0.08em]">below bar</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-4 max-w-[74ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
          Read it straight: <b className="font-semibold text-ink">B3 leads retrieval</b>, B4 matches B3 exactly on every
          retrieval metric, and B4 is the only rung whose groundedness falls under the {GUARDRAIL.toFixed(2)} guardrail
          — {suiteSummary.B4.groundedness.toFixed(3)} aggregate ({levelSummary.L2.B4.groundedness.toFixed(3)} on L2,{' '}
          {levelSummary.L3.B4.groundedness.toFixed(3)} on L3). The agent sometimes emits a citation that fails
          verification; those references are stripped from the delivered answer, but the score counts the draft before
          redaction, which is the point of measuring it that way. It is a real dip and it is reported as one.
        </p>

        {/* the per-level ladder — the finding that DID land */}
        <div className="mt-10">
          <h3 className="font-display text-[22px] font-medium tracking-[-0.01em]">
            The part that held up: <em className="italic text-brand">hybrid retrieval works.</em>
          </h3>
          <p className="mt-2 max-w-[68ch] text-[14.5px] leading-relaxed text-ink-2">
            H1 is a claim about the call graph, and that claim didn&rsquo;t clear the bar. But the rung below it did:
            sparse → dense → hybrid+rerank is a clean, monotonic ladder on the single-hop and cross-file levels. That
            result is independent of the H1 verdict and it replicated under real models.
          </p>
          <div className="mt-5 overflow-x-auto rounded-card border border-line bg-surface">
            <table className="w-full min-w-[560px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">
                  <th className="px-5 py-4 font-medium">Level · Recall@k</th>
                  {BASELINE_ORDER.map((b) => (
                    <th key={b} className="px-4 py-4 text-right font-medium">{b}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {LEVEL_ORDER.map((level) => (
                  <tr key={level} className="border-b border-line last:border-0">
                    <td className="px-5 py-4">
                      <span className="font-mono text-[13px] font-semibold text-ink-2">{level}</span>{' '}
                      <span className="font-display text-[15px] text-ink">{LEVEL_LABELS[level]}</span>
                      <span className="ml-2 font-mono text-[11px] text-ink-3">n={levelSummary[level].B4.questions}</span>
                    </td>
                    {BASELINE_ORDER.map((b) => (
                      <td key={b} className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">
                        {levelSummary[level][b].recallAtK.toFixed(3)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 max-w-[74ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
            Note the L3 row contradicts itself: sparse <Mono>B1</Mono> posts the{' '}
            <em>highest</em> L3 recall of any rung. On three questions that is almost certainly one lucky lexical hit,
            not evidence that BM25 understands architecture. It is left in because deleting inconvenient rows is how
            scoreboards start lying.
          </p>
        </div>
      </Section>

      {/* why the verdict reads the way it does */}
      <Section
        eyebrow="The diagnosis"
        title={<>The graph&rsquo;s contribution is <em className="italic text-brand">unmeasured</em>, not absent.</>}
        lede="Why B4 cannot currently beat B3 — and why that's a fact about the evaluation, not about the system."
      >
        <div className="grid grid-cols-[1.15fr_0.85fr] gap-6 max-[920px]:grid-cols-1">
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <p className="text-[15px] leading-relaxed text-ink-2">
              <b className="font-semibold text-ink">B4&rsquo;s scored retrieval is identical to B3&rsquo;s by
              construction.</b>{' '}
              The <Mono>retrieve()</Mono> call the harness measures is the same hybrid search in both rungs — which is
              why every retrieval cell in the two rows above matches to the digit. The call-graph tools fire later,{' '}
              <em>inside the agent&rsquo;s answer</em>, and the harness scores retrieval, not the answer. So the entire
              differentiator is invisible to Recall, MRR and nDCG.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-2">
              That leaves groundedness as the only channel where B4 can differ from B3 — and B4&rsquo;s groundedness
              dipped. Under this scoring{' '}
              <b className="font-semibold text-ink">B4 cannot beat B3, no matter how well the graph works.</b>
            </p>
            <p className="mt-4 border-l-2 border-brand pl-4 text-[14px] leading-relaxed text-ink-2">
              The honest phrasing matters here. This is not &ldquo;the graph didn&rsquo;t work&rdquo; or &ldquo;the
              graph wasn&rsquo;t validated.&rdquo; It is a diagnosed limitation of the measurement design: the harness
              never looked at the output the graph contributes to. Claiming either more or less than that would be
              inaccurate.
            </p>
          </div>
          <div className="rounded-card border border-line bg-surface p-7 max-[600px]:p-6">
            <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-3">
              What would re-open it
            </div>
            <ol className="space-y-3.5 text-[14px] leading-relaxed text-ink-2">
              <li>
                <b className="font-semibold text-ink">Score B4 on its final evidence set</b> — the verified citations
                attached to the answer, mapped to chunks by the same line-containment rule ground truth uses. B2/B3 keep
                their full top-5, so B4 gets <em>fewer</em> shots at the ground truth. The correction was chosen in the
                direction that makes it harder for B4, because that is the truthful one.
              </li>
              <li>
                <b className="font-semibold text-ink">Expand L3</b> from 3 to ~12 architecture questions, ground truth
                derived from code structure, human-reviewed for fair coverage — explicitly <em>not</em> screened for
                whether B4 can answer them — and committed before the re-run.
              </li>
              <li>
                <b className="font-semibold text-ink">Leave groundedness scoring alone.</b> Counting only
                post-redaction citations would push the score to ~1.00 by construction and could flip H1 for a purely
                cosmetic reason. That is not a bug fix.
              </li>
            </ol>
            <p className="mt-5 border-t border-line pt-4 font-mono text-[11px] leading-relaxed text-ink-3">
              Expanding the suite makes the re-run a fresh pre-registration: new questions and corrected scoring both
              fixed before any number is seen.
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
        title={<>{demoCases.length} of {questionCount} questions, every baseline.</>}
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
                taxonomy === level ? 'bg-brand text-white' : 'border border-line-2 text-ink-2 hover:bg-sunk'
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
                    active ? 'border-brand bg-brand-wash' : 'border-line bg-surface hover:border-line-2'
                  )}
                >
                  <div className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-3">{c.questionId}</div>
                  <div className="mt-1.5 font-display text-[15px] leading-snug text-ink">{c.question}</div>
                </button>
              );
            })}
          </aside>

          {selectedCase && (
            <div className="space-y-5">
              <div className="rounded-card border border-line bg-surface p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="font-display text-[20px] font-medium leading-snug text-ink">{selectedCase.question}</h3>
                  <span className="rounded-md bg-sunk px-2.5 py-1 font-mono text-[11px] text-ink-2">{selectedCase.taxonomy}</span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[12px] text-ink-3">
                  ground truth:
                  {selectedCase.gtFiles.map((f) => (
                    <span key={f} className="rounded-[5px] bg-good-wash px-1.5 py-px text-good">{f}</span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 max-[600px]:grid-cols-1">
                {BASELINE_ORDER.map((b) => {
                  const a = selectedCase.baselines[b];
                  const grounded = a.groundedness >= 0.95;
                  return (
                    <div key={b} className="rounded-card border border-line bg-surface p-5">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-display text-[16px] font-medium text-ink">
                          {b} <span className="font-mono text-[12px] text-ink-3">· {BASELINE_LABELS[b]}</span>
                        </span>
                        <span
                          className={cx(
                            'rounded-full border px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.06em]',
                            grounded ? 'border-good bg-good-wash text-good' : 'border-warn bg-warn-wash text-warn'
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
            Scope, plainly: {questionCount} questions on the {snapshotSource.corpus} corpus at k={snapshotSource.k},
            embedded with {snapshotSource.embedding}, reranked with {snapshotSource.reranker}, answers synthesised by{' '}
            {snapshotSource.synthesis}. One repository, one run, verdict written {snapshotSource.verdictWritten}{' '}
            (recovered, not recorded) — not a live or large-scale benchmark, and deliberately small enough to stay
            reproducible. Every number on this page is
            generated from <Mono>{snapshotSource.path}</Mono>, which is committed alongside this code; if a figure here
            disagrees with that directory, the directory is right.
          </p>
          <p className="mt-4 max-w-[74ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
            <b className="font-semibold text-ink">B0</b> (external code search) is absent from the ladder rather than
            scored zero: it needs an API token this run didn&rsquo;t have, so it is <em>not measured</em>. It has no
            bearing on the H1 verdict, which rests on B2, B3 and B4.
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

function MarginRow({ label, value, tone = 'neutral' }: { label: string; value: string; tone?: Tone }) {
  const toneClass: Record<Tone, string> = {
    neutral: 'text-ink',
    good: 'text-good',
    warn: 'text-warn',
    bad: 'text-bad',
  };
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[14px] text-ink-2">{label}</span>
      <span className={cx('font-mono text-[15px] font-semibold tabular-nums', toneClass[tone])}>{value}</span>
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
      <div className="mt-0.5 font-mono text-[13px] font-semibold tabular-nums text-ink">{value}</div>
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
          <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-ink-3">{eyebrow}</div>
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
