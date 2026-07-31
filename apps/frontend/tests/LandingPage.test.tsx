import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { externalKeywordBaseline, h1Report, suiteSummary } from '@/demo/evalSnapshot';
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

  it('discloses that B3 and B4 are scored by different rules', () => {
    // B4 now out-scores B3, so the old guardrail ("they tie") is gone. The
    // claim that has to stay pinned is the reason the rows differ: identical
    // retrieval, different scoring. A ladder showing B4 ahead without that
    // sentence would read as a clean win the run did not produce.
    expect(suiteSummary.B4.ndcgAtK).toBeGreaterThan(suiteSummary.B3.ndcgAtK);
    renderLanding();
    expect(screen.getByText(/B4 and B3 retrieve the same candidates/i)).toBeInTheDocument();
    expect(screen.getByText(/two scoring rules as well as two systems/i)).toBeInTheDocument();
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

  it('renders B0 without a bar, in the unit it actually retrieves in', () => {
    // B0 is measured now, and still gets no bar. The ladder plots nDCG over
    // chunks; B0 returns files and has no chunk-level result, so a bar would be
    // the invented number this section exists to avoid. The row states the
    // file-level figure and that it came from a live external index — the one
    // number on this page that cannot be regenerated from committed bytes.
    expect(externalKeywordBaseline).not.toBeNull();
    renderLanding();
    expect(screen.getByText(/file-level only/i)).toBeInTheDocument();
    expect(screen.getByText(/not reproducible/i)).toBeInTheDocument();
    expect(screen.queryByText(/not measured/i)).not.toBeInTheDocument();
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
