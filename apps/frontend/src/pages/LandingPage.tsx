import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { buttonClasses } from '@/components/ui';
import { cx } from '@/lib/cx';

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/** Fade + rise a block into view on scroll; shows immediately under reduced
 *  motion or where IntersectionObserver is unavailable (e.g. tests). */
function Reveal({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(
    () => typeof window === 'undefined' || prefersReducedMotion() || !('IntersectionObserver' in window)
  );

  useEffect(() => {
    if (shown) return;
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.14, rootMargin: '0px 0px -8% 0px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [shown]);

  return (
    <div
      ref={ref}
      className={cx(
        'transition-[opacity,transform] duration-700 ease-out',
        shown ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4',
        className
      )}
    >
      {children}
    </div>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" className={className} aria-hidden="true">
      <path d="M2.5 6.2l2.2 2.3 4.8-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface Stamp {
  file: string;
  loc: string;
}
// Real coordinates from the indexed psf/requests snapshot — the card's whole
// claim is "verified citations", so the numbers on it are true ones.
const STAMPS: Stamp[] = [
  { file: 'src/requests/auth.py', loc: 'line 85 · HTTPBasicAuth' },
  { file: 'src/requests/models.py', loc: 'line 670 · PreparedRequest.prepare_auth' },
];

/** The hero proof card: stamps animate verifying → verified, seal resolves to
 *  1.00. This is a marketing proof (not the product's live path) — the brief
 *  keeps it; reduced motion jumps straight to the verified end state. */
function ProofCard() {
  const [verified, setVerified] = useState<boolean[]>([false, false]);
  const [grounded, setGrounded] = useState(false);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setVerified([true, true]);
      setGrounded(true);
      return;
    }
    const timers = [
      setTimeout(() => setVerified((v) => [true, v[1]]), 1100),
      setTimeout(() => setVerified((v) => [v[0], true]), 1650),
      setTimeout(() => setGrounded(true), 2000),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <Reveal className="rounded-[18px] border border-line bg-surface p-6 shadow-[0_30px_60px_-34px_rgba(27,24,38,0.34)]">
      <div className="mb-[18px] flex items-center justify-between border-b border-line pb-4">
        <div className="flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.1em] text-good">
          <span className="h-2 w-2 rounded-full bg-good motion-reduce:animate-none" style={{ animation: 'dcode-ping 1.6s ease-out infinite' }} />
          agent · grounded
        </div>
        <div className="font-mono text-[12px] text-ink-2">
          groundedness <b className="font-semibold text-ink">{grounded ? '1.00' : '—'}</b>
        </div>
      </div>
      <p className="mb-5 font-display text-[19px] italic leading-snug text-ink">
        “How is authentication wired end to end?”
      </p>
      <p className="mb-5 font-display text-[15.5px] leading-relaxed text-ink-2">
        Requests attaches credentials through <b className="font-semibold text-ink">HTTPBasicAuth</b>, called on the
        prepared request in{' '}
        <span className="whitespace-nowrap rounded-[5px] bg-brand-wash px-1.5 py-px font-mono text-[12px] text-brand">
          auth.py:85
        </span>
        ; the flow resolves against{' '}
        <span className="whitespace-nowrap rounded-[5px] bg-brand-wash px-1.5 py-px font-mono text-[12px] text-brand">
          models.py
        </span>
        .
      </p>
      {STAMPS.map((stamp, i) => (
        <div
          key={stamp.file}
          className={cx(
            'mb-2.5 rounded-r-[10px] border border-l-[3px] border-line bg-paper px-[13px] py-[11px] transition-colors duration-300 last:mb-0',
            verified[i] ? 'border-l-good' : 'border-l-warn'
          )}
        >
          <div className="break-all font-mono text-[12px] text-ink">{stamp.file}</div>
          <div className="mt-0.5 font-mono text-[10.5px] text-ink-3">{stamp.loc}</div>
          <div
            className={cx(
              'mt-2 inline-flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.1em]',
              verified[i] ? 'text-good' : 'text-warn'
            )}
          >
            {verified[i] ? (
              <>
                <CheckIcon className="h-2.5 w-2.5" /> verified
              </>
            ) : (
              'verifying…'
            )}
          </div>
        </div>
      ))}
    </Reveal>
  );
}

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-paper text-ink">
      <style>{`@keyframes dcode-ping{0%{transform:scale(1);opacity:.7}100%{transform:scale(2.1);opacity:0}}`}</style>

      {/* masthead */}
      <header
        className={cx(
          'sticky top-0 z-40 border-b bg-[color-mix(in_srgb,var(--paper)_84%,transparent)] backdrop-blur-md transition-colors',
          scrolled ? 'border-line' : 'border-transparent'
        )}
      >
        <div className="mx-auto flex h-[70px] max-w-content items-center gap-8 px-8 max-[600px]:px-5">
          <Link to="/" className="flex items-baseline gap-2 font-display text-2xl font-semibold tracking-tight">
            Dcode<span className="h-[7px] w-[7px] -translate-y-0.5 rounded-full bg-brand" aria-hidden="true" />
          </Link>
          <nav className="ml-1.5 flex gap-1.5 max-[760px]:hidden">
            {[
              ['How it works', '#how'],
              ["Why it's different", '#why'],
              ['The evidence', '#rigor'],
            ].map(([label, href]) => (
              <a key={href} href={href} className="rounded-lg px-3 py-2 text-sm font-medium text-ink-2 transition hover:bg-sunk hover:text-ink">
                {label}
              </a>
            ))}
          </nav>
          <div className="flex-1" />
          <Link className={buttonClasses('primary', 'md')} to="/workbench">
            Open the demo <span className="font-mono text-xs opacity-70">→</span>
          </Link>
        </div>
      </header>

      {/* hero */}
      <section className="mx-auto max-w-content px-8 pb-[92px] pt-[76px] max-[600px]:px-5 max-[600px]:py-[52px]">
        <div className="grid grid-cols-[1.05fr_0.95fr] items-center gap-14 max-[920px]:grid-cols-1 max-[920px]:gap-11">
          <div>
            <Reveal>
              <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-ink-3">
                Structure-aware code retrieval
              </div>
            </Reveal>
            <Reveal>
              <h1 className="my-6 max-w-[15ch] font-display text-[clamp(42px,6.4vw,76px)] font-medium leading-[1.015] tracking-[-0.022em]">
                Understand any codebase — <em className="italic text-brand">then check the work.</em>
              </h1>
            </Reveal>
            <Reveal>
              <p className="mb-8 max-w-[52ch] font-display text-[clamp(18px,2.1vw,22px)] leading-[1.52] text-ink-2">
                You just inherited 200,000 lines you didn&rsquo;t write. Ask Dcode in plain English and get an answer
                where every reference points at real code — verified against the index before it reaches you.
              </p>
            </Reveal>
            <Reveal className="flex flex-wrap items-center gap-3">
              <Link className={buttonClasses('primary', 'lg')} to="/workbench">
                Open the demo <span className="font-mono text-xs opacity-70">↵</span>
              </Link>
              <a className={buttonClasses('ghost', 'lg')} href="#how">
                See how it works
              </a>
              <span className="ml-1 font-mono text-xs text-ink-3">no hallucinated citations</span>
            </Reveal>
          </div>
          <ProofCard />
        </div>
      </section>

      {/* tension */}
      <Section id="why" eyebrow="The problem" title={<>Search finds strings. Onboarding needs <em className="italic text-brand">structure.</em></>}
        lede={<>The questions that actually matter when you join a codebase are relational — <Mono>who calls this?</Mono>, <Mono>what breaks if I change it?</Mono> Text similarity can&rsquo;t see those.</>}>
        <Reveal className="grid grid-cols-2 overflow-hidden rounded-card border border-line bg-surface max-[920px]:grid-cols-1">
          <div className="border-r border-line p-[34px] max-[920px]:border-b max-[920px]:border-r-0 max-[600px]:p-[26px]">
            <div className="mb-[22px] flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">
              <span aria-hidden="true">◇</span>what today&rsquo;s tools give you
            </div>
            <ContrastRow t="Keyword search" d={<>Literal matches only. Miss <Mono>authenticate()</Mono> when you searched &ldquo;login&rdquo;.</>} />
            <ContrastRow t="Flat vector RAG" d="Text similarity that loses the call graph — no idea what depends on what." />
            <ContrastRow t="Generic chat assistants" d="Confident answers citing functions that don't exist." last />
          </div>
          <div className="p-[34px] max-[600px]:p-[26px]">
            <div className="mb-[22px] flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.14em] text-brand">
              <span aria-hidden="true">◆</span>what Dcode gives you
            </div>
            <ContrastRow t="Hybrid retrieval" d={<>Exact symbols <Mono>and</Mono> semantic intent, fused in one pass.</>} />
            <ContrastRow t="A real call graph" d="Definitions, references, and dependencies — the structure behind the question." />
            <ContrastRow t="Verified citations" d="Every reference checked against the index. Invented ones get stripped." last />
          </div>
        </Reveal>
      </Section>

      {/* how it works */}
      <Section id="how" eyebrow="The pipeline" title={<>Index. Ask. <em className="italic text-brand">Verify.</em></>}
        lede="One asynchronous path from a raw Git URL to an answer you can trust.">
        <Reveal className="grid grid-cols-3 gap-[22px] max-[920px]:grid-cols-1">
          <Step n="01" title="Index the repo" body={<>Clone, slice at <Mono>AST</Mono> boundaries, embed every symbol, and rebuild the call graph — a dual index of vectors and structure, colocated in one store.</>} />
          <Step n="02" title="Ask in plain English" body={<>A <Mono>ReAct</Mono> agent routes your question through hybrid retrieval and atomic graph queries, reasoning across files instead of matching one.</>} />
          <Step n="03" title="Verify before you read" body={<>Every citation in the answer is checked against the symbol table. Groundedness is measured, not promised — the guardrail holds it at <Mono>≥ 95%</Mono>.</>} last />
        </Reveal>
      </Section>

      {/* principles */}
      <Section eyebrow="Under the hood" title="Two indexes. One guardrail.">
        <Reveal className="grid grid-cols-3 gap-px overflow-hidden rounded-card border border-line bg-line max-[920px]:grid-cols-1">
          <Principle title="Structure-aware" tag="calls · imports · inherits · references"
            body="Cosine similarity tells you what code looks alike. A call graph tells you what actually calls what — so “trace this function’s callers” becomes a real answer." />
          <Principle title="Grounded, not confident" tag="groundedness ≥ 95%"
            body="The failure mode of code AI is a plausible symbol that doesn’t exist. Dcode extracts every citation, checks it against the index, and strips what it can’t verify." />
          <Principle title="Hybrid retrieval" tag="BM25 + dense + RRF + rerank"
            body="Code needs exact matching and semantic intent at once. Sparse and dense run in parallel, fused by rank, then reranked." />
        </Reveal>
      </Section>

      {/* rigor */}
      <section id="rigor" className="border-t border-line py-[92px] max-[600px]:py-[70px]">
        <div className="mx-auto grid max-w-content grid-cols-[0.95fr_1.05fr] items-center gap-[52px] px-8 max-[920px]:grid-cols-1 max-[600px]:px-5">
          <Reveal>
            <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-ink-3">The evidence</div>
            <h2 className="mt-4 font-display text-[clamp(30px,4.4vw,50px)] font-medium leading-[1.06] tracking-[-0.02em]">
              We tried to prove ourselves <em className="italic text-brand">wrong.</em>
            </h2>
            <p className="mt-[18px] max-w-[56ch] font-display text-[clamp(17px,2vw,20px)] leading-[1.5] text-ink-2">
              Most tools ship a demo. Dcode ships a falsifiable claim and a scoreboard.
            </p>
            <p className="mt-[26px] border-l-2 border-brand pl-[22px] font-display text-[clamp(15px,1.7vw,17px)] leading-[1.7] text-ink-2">
              The hypothesis: structure-aware retrieval beats flat RAG and keyword search on cross-file questions — by a
              margin set <b className="font-semibold text-ink">before</b> measuring, on a five-rung baseline ladder over
              standard IR metrics. If it doesn&rsquo;t clear the bar, the result is recorded{' '}
              <b className="font-semibold text-ink">unsupported</b>. The thresholds don&rsquo;t move after the numbers
              come in.
            </p>
          </Reveal>
          <Reveal className="rounded-card border border-line bg-surface p-[30px]">
            <div className="mb-[22px] font-mono text-[11px] uppercase tracking-[0.13em] text-ink-3">
              Baseline ladder · same questions, same metrics
            </div>
            {[
              ['B0', 'GitHub Search', 22, false],
              ['B1', 'BM25 sparse', 34, false],
              ['B2', 'Dense RAG', 58, false],
              ['B3', 'Hybrid + rerank', 72, false],
              ['B4', 'Dcode + graph + agent', 100, true],
            ].map(([rk, rn, width, top]) => (
              <div key={rk as string} className="flex items-center gap-4 border-b border-line py-[13px] last:border-0">
                <span className={cx('w-[26px] flex-none font-mono text-[12px] font-semibold', top ? 'text-brand' : 'text-ink-3')}>
                  {rk}
                </span>
                <span className="h-[9px] flex-1 overflow-hidden rounded-full bg-sunk">
                  <span className={cx('block h-full rounded-full', top ? 'bg-brand' : 'bg-line-2')} style={{ width: `${width}%` }} />
                </span>
                <span className={cx('w-[130px] flex-none font-display text-[15px]', top ? 'font-medium text-ink' : 'text-ink-2')}>
                  {rn}
                </span>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* closing */}
      <section className="border-t border-line py-[104px] text-center max-[600px]:py-[70px]">
        <div className="mx-auto max-w-content px-8 max-[600px]:px-5">
          <Reveal>
            <h2 className="mx-auto max-w-[18ch] font-display text-[clamp(34px,5.2vw,60px)] font-medium leading-[1.05] tracking-[-0.022em]">
              From a stranger&rsquo;s repo to <em className="italic text-brand">answers you can trust.</em>
            </h2>
            <p className="mx-auto mt-3 max-w-[48ch] font-display text-[19px] text-ink-2">
              Point it at a codebase. Ask the hard, relational questions. Read the receipts.
            </p>
            <div className="mt-[34px] flex flex-wrap justify-center gap-3">
              <Link className={buttonClasses('primary', 'lg')} to="/workbench">
                Open the demo <span className="font-mono text-xs opacity-70">↵</span>
              </Link>
              <a className={buttonClasses('ghost', 'lg')} href="https://github.com" target="_blank" rel="noreferrer">
                View on GitHub
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-line py-14">
        <div className="mx-auto flex max-w-content flex-wrap items-center justify-between gap-6 px-8 max-[600px]:px-5">
          <div className="font-display text-[19px] font-semibold">
            Dcode<span className="text-brand">.</span>
          </div>
          <div className="flex flex-wrap gap-3.5 font-mono text-xs text-ink-3">
            {['FastAPI', 'pgvector', 'LangGraph', 'RabbitMQ', 'React'].map((tech, i) => (
              <span key={tech}>
                {i > 0 && <span className="mr-3.5">·</span>}
                <span className="text-ink-2">{tech}</span>
              </span>
            ))}
          </div>
          <div className="font-mono text-xs text-ink-3">An independent research project · from idea to inference</div>
        </div>
      </footer>
    </div>
  );
}

function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono text-[0.9em] text-ink">{children}</span>;
}

function Section({
  id,
  eyebrow,
  title,
  lede,
  children,
}: {
  id?: string;
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="border-t border-line py-[92px] max-[600px]:py-[70px]">
      <div className="mx-auto max-w-content px-8 max-[600px]:px-5">
        <Reveal className="mb-[52px] max-w-[60ch]">
          <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-ink-3">{eyebrow}</div>
          <h2 className="mt-4 font-display text-[clamp(30px,4.4vw,50px)] font-medium leading-[1.06] tracking-[-0.02em]">
            {title}
          </h2>
          {lede && (
            <p className="mt-[18px] max-w-[56ch] font-display text-[clamp(17px,2vw,20px)] leading-[1.5] text-ink-2">
              {lede}
            </p>
          )}
        </Reveal>
        {children}
      </div>
    </section>
  );
}

function ContrastRow({ t, d, last }: { t: string; d: ReactNode; last?: boolean }) {
  return (
    <div className={cx('py-[15px]', !last && 'border-b border-line')}>
      <div className="mb-1 font-display text-[17px] text-ink">{t}</div>
      <div className="text-[13.5px] text-ink-2">{d}</div>
    </div>
  );
}

function Step({ n, title, body, last }: { n: string; title: string; body: ReactNode; last?: boolean }) {
  return (
    <div className="relative rounded-card border border-line bg-surface px-[26px] pb-7 pt-[30px]">
      <div className="mb-[18px] flex items-center gap-2.5 font-mono text-xs font-semibold tracking-[0.08em] text-brand">
        {n}
        <span className="h-px flex-1 bg-line" />
      </div>
      {!last && <span className="absolute -right-[15px] top-[38px] z-[2] bg-paper px-1 font-mono text-base text-ink-3 max-[920px]:hidden">→</span>}
      <h3 className="mb-2.5 font-display text-[22px] font-medium tracking-[-0.01em]">{title}</h3>
      <p className="text-sm leading-relaxed text-ink-2">{body}</p>
    </div>
  );
}

function Principle({ title, body, tag }: { title: string; body: string; tag: string }) {
  return (
    <div className="bg-surface p-[30px]">
      <h3 className="mb-2.5 font-display text-[21px] font-medium tracking-[-0.01em]">{title}</h3>
      <p className="text-sm leading-relaxed text-ink-2">{body}</p>
      <span className="mt-4 inline-block rounded-md bg-sunk px-2.5 py-1 font-mono text-[11px] text-ink-2">{tag}</span>
    </div>
  );
}
