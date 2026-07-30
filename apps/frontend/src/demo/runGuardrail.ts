/**
 * The groundedness bar the **recorded run** was judged against.
 *
 * This is not the runtime setting. `groundedness_threshold` in the backend
 * (overridable per deployment via `GROUNDEDNESS_THRESHOLD`) is what the agent
 * enforces *right now*. This is the line a finished, archived run was scored
 * against — fixed at the moment that run was judged, and unable to move
 * afterwards. The two are equal today by coincidence, not by construction.
 *
 * **Do not wire this to the backend settings or to an environment variable.**
 * That would let changing a deployment variable rewrite what a past run was
 * judged against — a rewrite of history arriving dressed as de-duplication,
 * which is exactly why it would be easy to approve.
 *
 * **This is a staging location, not the answer.** The value is a property of
 * the archived run, so it belongs in the generated snapshot, flowing out of the
 * run record like every other figure on these pages. The harness does not
 * record it yet — see `what_is_not_here` in `results/eval-real/provenance.json`.
 * This constant exists so that when the harness does record it, exactly one
 * place has to change instead of four.
 */
export const RUN_GROUNDEDNESS_BAR = 0.95;
