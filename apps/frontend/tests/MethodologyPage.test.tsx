import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { h1Report, levelSummary, suiteSummary } from '@/demo/evalSnapshot';
import MethodologyPage from '@/pages/MethodologyPage';

function renderMethodology() {
  return render(
    <MemoryRouter>
      <MethodologyPage />
    </MemoryRouter>
  );
}

describe('MethodologyPage', () => {
  it('reports the honest H1 verdict from the snapshot', () => {
    renderMethodology();
    expect(screen.getByText(/currently unsupported/i)).toBeInTheDocument();
    // B4's recorded groundedness, whatever it is — never an invented 1.00.
    expect(screen.getAllByText(suiteSummary.B4.groundedness.toFixed(3)).length).toBeGreaterThan(0);
  });

  it('discloses the B4 groundedness dip instead of burying it', () => {
    renderMethodology();
    // The real run put B4 under the 0.95 guardrail; the page has to say so.
    expect(suiteSummary.B4.groundedness).toBeLessThan(0.95);
    expect(screen.getByText(/below bar/i)).toBeInTheDocument();
  });

  it('names B3 as the retrieval leader, not B4', () => {
    // B4 matches B3 exactly on retrieval — the page must not imply B4 won.
    expect(suiteSummary.B4.ndcgAtK).toBe(suiteSummary.B3.ndcgAtK);
    renderMethodology();
    expect(screen.getByText(/B3 leads retrieval/i)).toBeInTheDocument();
  });

  it('flags L3 as statistically fragile at n=3', () => {
    expect(h1Report.comparisons.L3.questions).toBe(3);
    renderMethodology();
    expect(screen.getByText(/significance isn’t computable/i)).toBeInTheDocument();
  });

  it('frames the graph as unmeasured, never as failed', () => {
    renderMethodology();
    // Pin the framing positively rather than blacklisting phrasings: the page
    // legitimately quotes "the graph didn't work" in order to disclaim it.
    expect(screen.getByText('unmeasured')).toBeInTheDocument();
    expect(screen.getByText(/diagnosed limitation of the measurement design/i)).toBeInTheDocument();
  });

  it('features the validated hybrid-retrieval ladder', () => {
    // B1 < B2 < B3 on cross-file questions — the finding that did land.
    const l2 = levelSummary.L2;
    expect(l2.B1.recallAtK).toBeLessThan(l2.B2.recallAtK);
    expect(l2.B2.recallAtK).toBeLessThan(l2.B3.recallAtK);
    renderMethodology();
    expect(screen.getByText(/hybrid retrieval works/i)).toBeInTheDocument();
  });

  it('does not claim the page matches an unarchived run', () => {
    renderMethodology();
    // The old copy said "the numbers here match the recorded run" while matching
    // no committed artifact. It now names the directory it was generated from.
    expect(screen.getAllByText(/results\/eval-real\//).length).toBeGreaterThan(0);
  });

  it('routes the demo CTA into the workbench', () => {
    renderMethodology();
    expect(screen.getByRole('link', { name: /Open the demo/i })).toHaveAttribute('href', '/workbench');
  });

  it('switches question transcripts by taxonomy', () => {
    renderMethodology();
    // L2 is the default level -> a cross-file question is shown.
    expect(screen.getAllByText(/prepare a request before it is sent/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'L3' }));
    expect(screen.getAllByText(/end-to-end send flow/i).length).toBeGreaterThan(0);
  });
});
