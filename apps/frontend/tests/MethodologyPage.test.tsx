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

  it('does not present B4 leading retrieval as a clean win', () => {
    // B4 out-scores B3 for the first time, but on the same retrieved
    // candidates under a different scoring rule. The page may say B4 leads
    // only while it also says why the two rows are not comparable.
    expect(suiteSummary.B4.ndcgAtK).toBeGreaterThan(suiteSummary.B3.ndcgAtK);
    renderMethodology();
    expect(screen.getByText(/B3 and B4 retrieved the same candidates/i)).toBeInTheDocument();
    expect(screen.getByText(/scored on the evidence it ends up citing/i)).toBeInTheDocument();
  });

  it('keeps L3 flagged as fragile relative to the margin it missed', () => {
    // n grew 3 -> 12, so "significance isn't computable" no longer applies.
    // What still does: one question outweighs the gap to the bar.
    const n = h1Report.comparisons.L3.questions;
    expect(n).toBe(12);
    expect(1 / n).toBeGreaterThan(Math.abs(h1Report.threshold - h1Report.comparisons.L3.marginVsB3));
    renderMethodology();
    expect(screen.getByText(/one question still moves this level by up to/i)).toBeInTheDocument();
  });

  it('states the graph contribution as measured and small, not as unmeasured', () => {
    // The page said "unmeasured" for two runs. That became false the moment
    // the harness started counting structural ground-truth hits, so the
    // guardrail now pins the opposite claim and forbids the stale one.
    renderMethodology();
    expect(screen.queryByText('unmeasured')).not.toBeInTheDocument();
    expect(
      screen.getByText(/4 new ground-truth hits, across 3 of the 33 questions/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The ablation that would separate them does not exist yet/i)
    ).toBeInTheDocument();
  });

  it('reports the non-monotonic ladder instead of smoothing it', () => {
    // Sparse now out-recalls hybrid on both H1 levels, on 33 questions rather
    // than 3 — it can no longer be waved away as one lucky lexical hit.
    const { L2, L3 } = levelSummary;
    expect(L2.B1.recallAtK).toBeGreaterThan(L2.B3.recallAtK);
    expect(L3.B1.recallAtK).toBeGreaterThan(L3.B3.recallAtK);
    renderMethodology();
    expect(screen.getByText(/The BM25 rerun/i)).toBeInTheDocument();
    expect(screen.getByText(/ordering is not monotonic/i)).toBeInTheDocument();
    expect(screen.getByText(/stopped being explainable as/i)).toBeInTheDocument();
  });

  it('publishes that the verdict depends on the scoring rule', () => {
    // The single most omittable fact in this run: the pre-registered mixed
    // rule fails L3, the symmetric rule would clear it. If this sentence ever
    // disappears, the page is quietly reporting the convenient half.
    renderMethodology();
    expect(screen.getByText(/Scoring B3 by B4’s rule would clear/i)).toBeInTheDocument();
    expect(screen.getByText(/pre-registered rule is the one reported/i)).toBeInTheDocument();
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
