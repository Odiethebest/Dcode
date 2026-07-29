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
