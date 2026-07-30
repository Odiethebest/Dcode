import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { h1Report, suiteSummary } from '@/demo/evalSnapshot';
import { RUN_GROUNDEDNESS_BAR } from '@/demo/runGuardrail';
import LandingPage from '@/pages/LandingPage';

// Reduced motion so the proof card jumps straight to its verified end state
// (no timers left pending) and Reveal shows its content immediately.
function mockReducedMotion() {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('prefers-reduced-motion'),
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  );
}

describe('LandingPage', () => {
  beforeEach(() => mockReducedMotion());
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('leads with the hero promise', () => {
    renderLanding();
    expect(screen.getByRole('heading', { name: /Understand any codebase/i })).toBeInTheDocument();
  });

  it('routes every "Open the demo" CTA into the workbench', () => {
    renderLanding();
    const ctas = screen.getAllByRole('link', { name: /Open the demo/i });
    expect(ctas.length).toBeGreaterThan(0);
    for (const cta of ctas) {
      expect(cta).toHaveAttribute('href', '/workbench');
    }
  });

  it('settles the proof card to verified under reduced motion', () => {
    renderLanding();
    expect(screen.getAllByText(/^verified$/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/verifying/i)).not.toBeInTheDocument();
  });
});

/**
 * The ladder used to be stylised marketing — hardcoded 22/34/58/72/100 with B4
 * maxed out — while /methodology reported H1 unsupported. The front page said
 * "we won" and one click deeper said "we haven't yet".
 */
describe('LandingPage baseline ladder', () => {
  beforeEach(() => mockReducedMotion());

  it('draws every bar from the recorded snapshot', () => {
    const { container } = renderLanding();
    for (const b of ['B1', 'B2', 'B3', 'B4'] as const) {
      // getAll: B3 and B4 print the same score, because they genuinely tie.
      expect(screen.getAllByText(suiteSummary[b].ndcgAtK.toFixed(3)).length).toBeGreaterThan(0);
    }
    // No bar is full-width: nothing on this page maxes the scale any more.
    const widths = [...container.querySelectorAll<HTMLElement>('[style*="width"]')].map(
      (el) => el.style.width
    );
    expect(widths).not.toContain('100%');
    expect(widths).not.toContain('100.0%');
  });

  it('never shows B4 beating B3 — they tie on retrieval', () => {
    expect(suiteSummary.B4.ndcgAtK).toBe(suiteSummary.B3.ndcgAtK);
    renderLanding();
    expect(screen.getByText(/B4 ties B3 on retrieval/i)).toBeInTheDocument();
  });

  it('states the H1 verdict plainly and links to the methodology', () => {
    renderLanding();
    expect(h1Report.decision).toBe('unsupported');
    expect(screen.getByText(new RegExp(`H1 — ${h1Report.decision}`, 'i'))).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /full methodology/i })).toHaveAttribute(
      'href',
      '/methodology'
    );
  });

  it('renders B0 as not measured, with no bar', () => {
    renderLanding();
    // A concrete bar for a baseline that was never run is the least defensible
    // number on the page — B0 gets a row and an explanation instead.
    expect(screen.getByText(/not measured · requires an API token/i)).toBeInTheDocument();
  });
});

/**
 * The pipeline section used to assert "the guardrail holds it at ≥ 95%" and tag a
 * principle `groundedness ≥ 95%`, while the recorded run came in under that bar —
 * and while the ladder further down this same page reported the dip. A
 * pre-registered threshold is only worth stating if it is allowed to fail, so the
 * copy states the commitment and the miss instead of the guarantee.
 */
describe('LandingPage groundedness guardrail claim', () => {
  beforeEach(() => mockReducedMotion());

  it('never claims the pre-registered bar was met', () => {
    // The assertions below only mean something while the run is actually under
    // the bar; pin that precondition rather than assuming it.
    expect(suiteSummary.B4.groundedness).toBeLessThan(RUN_GROUNDEDNESS_BAR);

    const { container } = renderLanding();
    const copy = container.textContent ?? '';
    expect(copy).not.toMatch(/guardrail holds it at/i);
    expect(copy).not.toMatch(/groundedness\s*≥\s*95\s*%/i);
    // The bar is named as a pre-registered commitment, and the miss is stated.
    expect(copy).toContain(`fixed at ${RUN_GROUNDEDNESS_BAR.toFixed(2)} before the run`);
    expect(copy).toMatch(/came in under it/i);
  });

  it('reads the missed value from the snapshot rather than restating it', () => {
    // An earlier pass pointed at the ladder instead of naming the number. A
    // sentence that points at a location is a copy of the page layout and rots
    // in silence, so the value is bound. Pin the binding, not the digits: a
    // hand-typed literal here would survive a re-run and quietly disagree with
    // the ladder in the same card.
    const { container } = renderLanding();
    expect(container.textContent ?? '').toContain(
      `came in under it at ${suiteSummary.B4.groundedness.toFixed(3)}`
    );
  });
});
