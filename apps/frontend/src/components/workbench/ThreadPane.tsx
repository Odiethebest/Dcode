const SUGGESTIONS = ['Who calls HTTPBasicAuth?', 'What breaks if I change prepare_auth?'];

/**
 * Center conversation pane: scrolling thread + pinned composer. The thread body
 * is an empty state here; real turns (streamed SSE) are wired in slice 3, and
 * the composer becomes functional then. Structure/voice are final.
 */
export function ThreadPane() {
  return (
    <main className="relative flex min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto py-2">
        <div className="mx-auto max-w-[720px] px-10 max-[760px]:px-[22px]">
          <div className="flex min-h-[52vh] flex-col items-center justify-center text-center">
            <h1 className="font-display text-4xl font-medium tracking-tight text-ink">
              Ask this codebase anything
            </h1>
            <p className="mt-3 max-w-md font-display text-lg leading-relaxed text-ink-2">
              Every answer streams its reasoning and cites real, verified code you can open on the right.
            </p>
          </div>
        </div>
      </div>

      <div className="flex-none border-t border-line bg-[color-mix(in_srgb,var(--paper)_80%,transparent)] py-3.5 backdrop-blur-[8px]">
        <div className="mx-auto max-w-[720px] px-10 max-[760px]:px-[22px]">
          <div className="flex flex-wrap gap-2 pb-2.5">
            {SUGGESTIONS.map((text) => (
              <button
                key={text}
                type="button"
                className="rounded-full border border-line-2 bg-surface px-3 py-1.5 text-[12.5px] text-ink-2 transition hover:border-brand hover:bg-brand-wash hover:text-brand"
              >
                {text}
              </button>
            ))}
          </div>

          <div className="flex items-end gap-2.5 rounded-[14px] border border-line-2 bg-surface p-2 pl-4 transition focus-within:border-brand focus-within:shadow-[0_0_0_3px_var(--brand-wash)]">
            <textarea
              rows={1}
              placeholder="Ask a question about this repo…"
              spellCheck={false}
              className="max-h-[120px] flex-1 resize-none bg-transparent py-2 font-sans text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-3"
            />
            <button
              type="button"
              aria-label="Send"
              className="flex h-10 w-10 flex-none items-center justify-center rounded-[10px] bg-brand text-white transition hover:bg-brand-hover"
            >
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M10 16V4M5 9l5-5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>

          <p className="mt-2.5 text-center font-mono text-[10.5px] text-ink-3">
            answers stay in this thread · every citation is verified before it appears
          </p>
        </div>
      </div>
    </main>
  );
}
