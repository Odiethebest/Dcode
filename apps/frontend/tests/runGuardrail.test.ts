import { describe, expect, it } from 'vitest';

import { snapshotSource } from '@/demo/evalSnapshot';
import { RUN_GROUNDEDNESS_BAR } from '@/demo/runGuardrail';

/**
 * Page predicates have to use the same bar the page renders. Importing a
 * duplicated constant in both production code and tests would let the two move
 * together while remaining wrong, so the alias is checked against the generated
 * run source.
 *
 * The generated snapshot now carries the value from committed run provenance,
 * so this test pins the page-facing alias to that recorded source rather than
 * duplicating a literal.
 */
describe('RUN_GROUNDEDNESS_BAR', () => {
  it('is the bar the recorded run was actually judged against', () => {
    expect(RUN_GROUNDEDNESS_BAR).toBe(snapshotSource.groundednessGuardrail);
  });
});
