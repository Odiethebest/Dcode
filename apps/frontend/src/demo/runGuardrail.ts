import { snapshotSource } from '@/demo/evalSnapshot';

/**
 * The groundedness bar the **recorded run** was judged against.
 *
 * This is not the runtime setting. `groundedness_threshold` in the backend
 * (overridable per deployment via `GROUNDEDNESS_THRESHOLD`) is what the agent
 * enforces *right now*. This is the line the finished, recorded run was scored
 * against — fixed at the moment that run was judged, and unable to move
 * afterwards. The two are equal today by coincidence, not by construction.
 *
 * **Do not wire this to the backend settings or to an environment variable.**
 * That would let changing a deployment variable rewrite what a past run was
 * judged against — a rewrite of history arriving dressed as de-duplication,
 * which is exactly why it would be easy to approve.
 *
 * The value is a property of the recorded run and therefore flows from the
 * generated snapshot, whose provenance records it outside the harness output:
 * `results/eval-h1-bm25-2026-07-30/provenance.json`.
 */
export const RUN_GROUNDEDNESS_BAR = snapshotSource.groundednessGuardrail;
