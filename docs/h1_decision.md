# H1 Decision

## Decision

**H1 remains unsupported** on the current recorded evaluation suite.

## Basis

Question set:

- repository: `requests`
- size: 16 questions
- focus: L1 / L2 / L3 curated code-understanding tasks

Acceptance rule:

- B4 must beat both B2 and B3 by at least `0.05` composite points on both L2 and L3

Observed result from `results/eval-suite/h1_report.json`:

- `L2 margin vs B2 = -0.0125`
- `L2 margin vs B3 = -0.0125`
- `L3 margin vs B2 = -0.0333`
- `L3 margin vs B3 = -0.0333`

B4 therefore failed the acceptance rule on both target taxonomies.

This decision is scoped to the checked-in `results/eval-suite/` snapshot. The
snapshot has not yet been regenerated after enabling the real embedding and
reranker sidecar path.

## Interpretation

The current stack is a valid engineering baseline, but not yet evidence for the original hypothesis.

Most likely reasons:

1. the recorded suite was produced before a fresh real embedding/reranker evaluation
2. default local configuration still uses stub embedding and identity rerank
3. the eval harness does not yet cleanly isolate dense-only, sparse-only, hybrid, and full-system retrieval paths
4. the graph remains shallow beyond best-effort imports and calls
5. planner / synthesize remain rule/template-based

## Required To Re-open H1

- re-index the target repo with real code embeddings and matching `EMBEDDING_DIM`
- enable the reranker and record its configuration
- separate the baseline retrieval paths in the eval harness
- deepen graph edges where they materially support L2/L3 questions
- rerun the same suite or a stronger versioned successor

Until then, the honest project conclusion remains: **unsupported**.
