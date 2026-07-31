import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import {
  demoCases,
  h1Report,
  levelSummary,
  snapshotSource,
  suiteSummary,
} from '@/demo/evalSnapshot';
import { RUN_GROUNDEDNESS_BAR } from '@/demo/runGuardrail';
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

  it('reports that B4 clears the recorded groundedness guardrail', () => {
    renderMethodology();
    expect(suiteSummary.B4.groundedness).toBeGreaterThanOrEqual(RUN_GROUNDEDNESS_BAR);
    expect(screen.queryByText(/below bar/i)).not.toBeInTheDocument();
    expect(screen.getByText(/every rung clears/i)).toBeInTheDocument();
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

  it('shows the corrected BM25 ladder without claiming monotonicity', () => {
    const l2 = levelSummary.L2;
    expect(l2.B1.recallAtK).toBeGreaterThan(l2.B2.recallAtK);
    expect(l2.B1.recallAtK).toBeLessThan(l2.B3.recallAtK);
    renderMethodology();
    expect(screen.getByText(/The BM25 rerun/i)).toBeInTheDocument();
    expect(screen.getByText(/ordering is not monotonic/i)).toBeInTheDocument();
  });

  it('does not claim the page matches an unarchived run', () => {
    renderMethodology();
    // The old copy said "the numbers here match the recorded run" while matching
    // no committed artifact. It now names the directory it was generated from.
    expect(screen.getAllByText(snapshotSource.path).length).toBeGreaterThan(0);
  });

  it('routes the demo CTA into the workbench', () => {
    renderMethodology();
    expect(screen.getByRole('link', { name: /Open the demo/i })).toHaveAttribute(
      'href',
      '/workbench'
    );
  });

  it('titles the transcripts with their real scope, not the whole suite', () => {
    // The section renders a fixed excerpt but was headed "Every question, every
    // baseline." The honest scope existed in the footnote; the prominent line
    // was the flattering one. Both counts come from the generated snapshot.
    expect(demoCases.length).toBeLessThan(suiteSummary.B4.questions);
    const { container } = renderMethodology();
    const copy = container.textContent ?? '';
    expect(copy).not.toMatch(/every question, every baseline/i);
    expect(copy).toContain(`${demoCases.length} of ${suiteSummary.B4.questions} questions`);
  });

  it('switches question transcripts by taxonomy', () => {
    renderMethodology();
    // L2 is the default level -> a cross-file question is shown.
    expect(screen.getAllByText(/prepare a request before it is sent/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'L3' }));
    expect(screen.getAllByText(/end-to-end send flow/i).length).toBeGreaterThan(0);
  });
});
