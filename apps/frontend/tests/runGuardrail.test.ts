import { describe, expect, it } from 'vitest';

import { RUN_GROUNDEDNESS_BAR } from '@/demo/runGuardrail';

/**
 * The page tests assert "while the run is under the bar, the page must disclose
 * it" against this constant, which is correct — the predicate has to use the
 * same bar the page renders. But that leaves a hole those tests cannot close: a
 * test that imports the constant under test can never catch the constant itself
 * being wrong. Set it to 0.50 and the page, the predicate and the assertion all
 * move together, still green.
 *
 * So the literal is pinned here, once. This is a fact about the past — 0.95 is
 * the line the archived run was judged against, and nothing can change that
 * retroactively. Pinning it is this test's entire job, and this is the only
 * place in the frontend that should do it.
 *
 * Lifecycle: once the harness records the threshold into the run record (see
 * `what_is_not_here` in results/eval-real/provenance.json), this becomes "the
 * constant equals the value in the run record", and then it is deleted along
 * with src/demo/runGuardrail.ts.
 */
describe('RUN_GROUNDEDNESS_BAR', () => {
  it('is the bar the recorded run was actually judged against', () => {
    // Changing this requires provenance for a different run — it is not a
    // configuration decision, and it is not the runtime threshold.
    expect(RUN_GROUNDEDNESS_BAR).toBe(0.95);
  });
});
