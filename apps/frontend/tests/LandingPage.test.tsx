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

  /**
   * The card mimics the product on four axes — real file:line coordinates, a
   * plausible answer, the same stamps, the same seal — so unlabelled it is
   * indistinguishable from a screenshot of a real answer. Nothing on it was
   * false, which is why the "generated numbers" and "never fabricate" rules both
   * had nothing to say about it. See Honesty_Constraints §12.
   */
  it('identifies the proof card as an illustration and shows no metric-shaped figure', () => {
    renderLanding();
    expect(screen.getByText(/not a live answer/i)).toBeInTheDocument();
    // 1.00 was arithmetically right for its own mock citations and still the
    // most flattering figure on a page arguing that it reports its misses.
    expect(screen.queryByText('1.00')).not.toBeInTheDocument();
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
 * principle `groundedness ≥ 95%`, turning a threshold into a guarantee. The
 * current run clears that bar, but the copy still states the measured outcome
 * rather than promising that every future run must do so.
 */
describe('LandingPage groundedness guardrail claim', () => {
  beforeEach(() => mockReducedMotion());

  it('reports that the current run cleared the pre-registered bar', () => {
    expect(suiteSummary.B4.groundedness).toBeGreaterThanOrEqual(RUN_GROUNDEDNESS_BAR);

    const { container } = renderLanding();
    const copy = container.textContent ?? '';
    expect(copy).not.toMatch(/guardrail holds it at/i);
    expect(copy).not.toMatch(/groundedness\s*≥\s*95\s*%/i);
    // The bar is named as a pre-registered commitment, and this run's outcome is stated.
    expect(copy).toContain(`fixed at ${RUN_GROUNDEDNESS_BAR.toFixed(2)} before the run`);
    expect(copy).toMatch(/cleared it/i);
  });

  it('reads the measured value from the snapshot rather than restating it', () => {
    const { container } = renderLanding();
    expect(container.textContent ?? '').toContain(
      `cleared it at ${suiteSummary.B4.groundedness.toFixed(3)}`
    );
  });
});
