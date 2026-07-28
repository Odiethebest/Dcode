import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { buttonClasses } from '@/components/ui';
import {
  demoCases,
  h1Report,
  suiteSummary,
  type BaselineName,
  type Taxonomy,
} from '@/demo/evalSnapshot';
import { cx } from '@/lib/cx';

const BASELINE_ORDER: BaselineName[] = ['B1', 'B2', 'B3', 'B4'];
const TAXONOMY_ORDER: Taxonomy[] = ['L2', 'L3'];

const BASELINE_LABELS: Record<BaselineName, string> = {
  B1: 'BM25 sparse',
  B2: 'Dense RAG',
  B3: 'Hybrid + rerank',
  B4: 'Dcode + graph + agent',
};

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
          and the current result are all below — read straight from a fixed local evaluation snapshot ({questionCount}{' '}
          questions), never invented for this page.
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
            bar is <Mono>+{h1Report.threshold.toFixed(2)}</Mono> over <em>both</em> B2 and B3.
          </>
        }
      >
        <div className="grid grid-cols-2 gap-5 max-[760px]:grid-cols-1">
          {TAXONOMY_ORDER.map((level) => {
            const c = h1Report.comparisons[level];
            return (
              <div key={level} className="rounded-card border border-line bg-surface p-6">
                <div className="flex items-center justify-between">
                  <span className="font-display text-[22px] font-medium">{level} questions</span>
                  <span
                    className={cx(
                      'rounded-full border px-3 py-1 font-mono text-[10.5px] font-medium uppercase tracking-[0.08em]',
                      c.supported ? 'border-good bg-good-wash text-good' : 'border-warn bg-warn-wash text-warn'
                    )}
                  >
                    {c.supported ? 'cleared' : 'did not clear'}
                  </span>
                </div>
                <div className="mt-5">
                  <MarginRow label="B4 composite" value={c.baselineComposite.toFixed(3)} />
                  <MarginRow label="margin vs B2 · Dense RAG" value={signed(c.marginVsB2)} tone={marginTone(c.marginVsB2)} />
                  <MarginRow label="margin vs B3 · Hybrid + rerank" value={signed(c.marginVsB3)} tone={marginTone(c.marginVsB3)} />
                </div>
                <p className="mt-4 border-t border-line pt-4 font-mono text-[11px] text-ink-3">
                  bar · both margins ≥ +{h1Report.threshold.toFixed(2)}
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
                const top = b === 'B4';
                return (
                  <tr key={b} className={cx('border-b border-line last:border-0', top && 'bg-brand-wash')}>
                    <td className="px-5 py-4">
                      <div className={cx('font-mono text-[13px] font-semibold', top ? 'text-brand' : 'text-ink-2')}>{b}</div>
                      <div className="font-display text-[15px] text-ink">{BASELINE_LABELS[b]}</div>
                    </td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">{s.recallAtK.toFixed(3)}</td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">{s.mrr.toFixed(3)}</td>
                    <td className="px-4 py-4 text-right font-mono text-[14px] tabular-nums text-ink">{s.ndcgAtK.toFixed(3)}</td>
                    <td className="px-5 py-4 text-right font-mono text-[14px] tabular-nums text-ink">{s.groundedness.toFixed(3)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-4 max-w-[72ch] font-mono text-[11.5px] leading-relaxed text-ink-3">
          The honest shape of it: B2 (dense RAG) leads on recall and nDCG here, and B4 matches B3 on retrieval while its
          groundedness dips to {suiteSummary.B4.groundedness.toFixed(3)}. That&rsquo;s exactly why the bar was
          pre-registered — the current snapshot doesn&rsquo;t support H1, and the number stands as recorded.
        </p>
      </Section>

      {/* the transcripts */}
      <Section
        eyebrow="The transcripts"
        title="Every question, every baseline."
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
            This is a fixed snapshot of the local H1 evaluation suite — {questionCount} questions on the psf/requests
            corpus — not a live or large-scale benchmark. It is deliberately small and reproducible so the demo stays
            stable and the claim stays honest. The numbers here match the recorded run; the copy matches the README.
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
