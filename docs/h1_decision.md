# H1 Decision

## Decision

**H1 is unsupported** on the current recorded evaluation suite.

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

## Interpretation

The current stack is a valid engineering baseline, but not yet evidence for the original hypothesis.

Most likely reasons:

1. query-side dense retrieval is still effectively disabled in the default stack
2. reranking is still identity
3. the graph is still shallow, centered on definitions and module imports
4. planner / synthesize remain rule/template-based

## Required To Re-open H1

- connect real code embedding for retrieval
- connect real reranking
- deepen graph edges
- rerun the same suite or a stronger versioned successor

Until then, the honest project conclusion remains: **unsupported**.
