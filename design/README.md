# Design prototypes

Two standalone HTML files. Open either in a browser — no build step, no server.

| File | What it is |
|---|---|
| [`dcode-workbench.html`](dcode-workbench.html) | The product: three-pane exploration workbench — repo switcher, conversational thread, code + call-graph inspector. Became `/workbench`. |
| [`dcode-landing.html`](dcode-landing.html) | The marketing landing page. Became `/`. |

**These are still the visual authority.** They were not throwaway mockups: the
shipped React UI was reimplemented from them component by component, and they
remain the reference for questions like "how wide is the right rail", "what
weight is that eyebrow label", "how much air above a heading". If the
implementation and a prototype disagree on appearance, the prototype is probably
right — check before changing either.

The colour tokens, the three-font split, and the layout proportions were chosen
deliberately to avoid a generic default look. They are documented in
[`../CLAUDE.md`](../CLAUDE.md) §3, and the live implementation renders every
shared primitive at `/preview` for side-by-side comparison.

**They are not the authority on data or behaviour.** Both files mock the SSE
stream, the groundedness score, the source contents, and the call-graph edges,
because they had no backend. The shipped UI is driven by real endpoints only —
see [`../docs/en/Honesty_Constraints.md`](../docs/en/Honesty_Constraints.md) for
the rules that govern what it is allowed to display, several of which exist
precisely because the prototype's convenient fiction would have been dishonest in
a real product. Notably, the prototype's inspector header always shows a
`verified` badge; the real one only shows it where a citation actually passed
verification.

The brief that drove the rebuild is archived at
[`../docs/archive/frontend-redesign-brief.md`](../docs/archive/frontend-redesign-brief.md).
Its four phases are all complete, so it is history rather than instruction.

## Recorded divergences

Where the shipped UI has deliberately departed from a prototype, it is listed
here. These are **not** sync debt, and the HTML is deliberately left alone: a
prototype that has to be kept in step is itself a hand-maintained copy, which is
the defect this repository keeps paying for. The prototypes are the historical
visual reference for the rebuild, not a live mirror. Recording a divergence
turns it into a fact; back-porting it would turn it into an obligation.

| Prototype | Shipped | Why |
|---|---|---|
| `dcode-workbench.html` inspector header always shows a `verified` badge | badge only where a citation actually passed verification | The prototype had no backend to fail against. [Honesty_Constraints.md](../docs/en/Honesty_Constraints.md) §5 |
| `dcode-landing.html:225,402,410` — hero seal resolves to `groundedness 1.00` | seal resolves to a word; no figure | A metric-shaped number with no run behind it, and the first groundedness value on a page whose argument is that it reports its misses. §12 |
| `dcode-landing.html` hero card carries no marker | card leads with `Example — not a live answer` | The card mimics the product down to real `file:line` coordinates; unlabelled it is indistinguishable from a screenshot of a real answer. §12 |
| `dcode-landing.html:286,310` — `the guardrail holds it at ≥ 95%` | states the bar was pre-registered and that this run missed it | The recorded run came in under the bar. §11 |
