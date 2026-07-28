import type { ReactNode } from 'react';

import {
  Button,
  CitationChip,
  CodeChip,
  StatusPill,
  VerifiedMark,
} from '@/components/ui';

// Temporary Phase 1 review page — not wired into the app IA. Renders every
// primitive in its states so the identity can be eyeballed before Phase 2.
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-3 border-b border-line py-6 last:border-0 sm:grid-cols-[9rem_1fr] sm:items-center">
      <div className="font-mono text-[11px] uppercase tracking-wide text-ink-3">{label}</div>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}

export default function PrimitivesGallery() {
  return (
    <div className="min-h-screen bg-paper px-8 py-12 text-ink">
      <div className="mx-auto max-w-content">
        <header className="mb-10">
          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-3">
            Dcode · design system
          </div>
          <h1 className="mt-3 font-display text-5xl font-medium tracking-tight">
            Phase 1 primitives — <em className="text-brand">check the identity</em>
          </h1>
          <p className="mt-3 max-w-2xl font-display text-lg leading-relaxed text-ink-2">
            Cool paper, deep indigo, and the two-voice split: Newsreader for understanding,
            IBM Plex Mono for{' '}
            <span className="font-mono text-base text-ink">machine-verified evidence</span>.
          </p>
        </header>

        <section className="rounded-card border border-line bg-surface p-8 shadow-sm">
          <Row label="Button">
            <Button>Open the demo</Button>
            <Button size="lg">Open the demo</Button>
            <Button variant="ghost">See how it works</Button>
            <Button variant="ghost" size="lg">
              See how it works
            </Button>
            <Button disabled>Disabled</Button>
          </Row>

          <Row label="StatusPill">
            <StatusPill status="ready" />
            <StatusPill status="indexing" label="indexing · embedding" />
            <StatusPill status="failed" />
          </Row>

          <Row label="VerifiedMark">
            <VerifiedMark verified />
            <VerifiedMark verified={false} />
          </Row>

          <Row label="CodeChip">
            <span className="font-display text-lg text-ink">
              attaches credentials in <CodeChip>HTTPBasicAuth.__call__</CodeChip>, delegating to{' '}
              <CodeChip>_basic_auth_str</CodeChip>
            </span>
          </Row>

          <Row label="CitationChip">
            <CitationChip>auth.py:85</CitationChip>
            <span className="text-sm text-ink-3">active →</span>
            <CitationChip active>models.py:471</CitationChip>
            <span className="text-sm text-ink-3">unverified →</span>
            <CitationChip verified={false}>utils.py:1042</CitationChip>
            <CitationChip verified={false} active>
              legacy.py:0
            </CitationChip>
          </Row>

          <Row label="In prose">
            <p className="max-w-2xl font-display text-lg leading-relaxed text-ink">
              For basic auth that object is <CodeChip>HTTPBasicAuth</CodeChip>: its{' '}
              <CodeChip>__call__</CodeChip> sets the header <CitationChip>auth.py:85</CitationChip>,
              and the flow resolves in <CitationChip active>models.py:471</CitationChip>.
            </p>
          </Row>
        </section>
      </div>
    </div>
  );
}
