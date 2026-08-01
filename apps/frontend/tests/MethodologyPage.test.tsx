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

  it('states each level\'s single-question weight, whether or not it cleared', () => {
    // L3 now clears, so "it missed by less than one question" no longer applies
    // to it. The weight is still what a reader needs to judge either level, and
    // it is still larger than the bar on both.
    for (const level of ['L2', 'L3'] as const) {
      expect(1 / h1Report.comparisons[level].questions).toBeGreaterThan(h1Report.threshold);
    }
    renderMethodology();
    expect(screen.getAllByText(/one question moves this level by up to/i).length).toBe(2);
  });

  it('states the graph contribution as measured and small, not as unmeasured', () => {
    // The page said "unmeasured" for two runs. That became false the moment
    // the harness started counting graph-sourced ground-truth hits, so the
    // guardrail pins the opposite claim and forbids the stale one.
    renderMethodology();
    expect(screen.queryByText('unmeasured')).not.toBeInTheDocument();
    expect(screen.getByText(/positive, consistent across both levels, and small/i)).toBeInTheDocument();
    // The ablation now exists, so the page must attribute the split rather than
    // decline to. Claiming the whole B4-B3 gap for the graph is the easy lie
    // here, and B3.5 is what makes it a checkable one.
    expect(
      screen.getByText(/multi-step evidence gathering is worth several times the graph/i)
    ).toBeInTheDocument();
  });

  it('carries no hand-typed snapshot figure in the diagnosis prose', () => {
    // This paragraph used to read "14 new ground-truth hits across 10 of the 33
    // questions", "+0.022", "+0.023" and "+0.147" — every one of them typed by
    // hand, none inside a generated block, and the only thing checking them was
    // this file asserting the same literals back. Two copies of a number drift
    // together and the drift check never sees it, which is the exact failure
    // Honesty_Constraints section 11 exists to prevent.
    //
    // So the rule for this section is: qualitative claims in prose, figures
    // named by their field and their file. If a specific margin has to appear
    // here, it goes in a generated block first.
    const { container } = renderMethodology();
    const diagnosis = screen.getByText(/multi-step evidence gathering/i).closest('div');
    expect(diagnosis).not.toBeNull();
    expect(diagnosis!.textContent).not.toMatch(/[+-]0\.\d{3}/);
    expect(container.textContent).not.toMatch(/\d+ new ground-truth hits/);
  });

  it('reports the surviving ladder inversion instead of smoothing it', () => {
    // The ladder climbs on L2 now. It did not before test code was excluded,
    // and one inversion is left on L3 — sparse still edges dense. Reporting the
    // fixed ordering while quietly dropping the leftover would be the tidy lie.
    const { L2, L3 } = levelSummary;
    expect(L2.B1.recallAtK).toBeLessThan(L2.B3.recallAtK);
    expect(L3.B1.recallAtK).toBeGreaterThan(L3.B2.recallAtK);
    renderMethodology();
    expect(screen.getByText(/The BM25 rerun/i)).toBeInTheDocument();
    expect(screen.getByText(/One inversion survives/i)).toBeInTheDocument();
  });

  it('publishes that one repeat cleared the bar on its own', () => {
    // The single most omittable fact in this run, and it replaced a different
    // one. The page used to say the verdict hinged on B2/B3 being scored by a
    // different rule than B4 — true under `v1`, false since every agent arm
    // moved to one rule, and it outlived that change because prose is not
    // covered by the drift check.
    //
    // What makes this verdict fragile now is measured, not asserted: the
    // deciding margin's spread across identical repeats is wider than the bar,
    // and one repeat returned `supported` alone. Reporting the mean while
    // omitting that is reporting the convenient half.
    const supported = h1Report.perRepeat.filter((r) => r.decision === 'supported').length;
    expect(supported).toBeGreaterThan(0);
    renderMethodology();
    expect(
      screen.getByText(new RegExp(`${supported} of ${h1Report.repeats} repeats returned`, 'i'))
    ).toBeInTheDocument();
    expect(screen.getByText(/wider than the/i)).toBeInTheDocument();
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
