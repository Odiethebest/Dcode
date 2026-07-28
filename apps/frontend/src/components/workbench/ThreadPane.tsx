import { useEffect, useRef, useState } from 'react';

import type { CitationPayload } from '@/api/types';
import { Turn } from '@/components/workbench/Turn';
import type { Turn as TurnData } from '@/hooks/useThread';
import { cx } from '@/lib/cx';

const SUGGESTIONS = ['Who calls HTTPBasicAuth?', 'What breaks if I change prepare_auth?'];

// The one reading axis: empty state, answers, and composer share this centered
// column inside the 1fr center pane.
const readingColumn = 'mx-auto w-full max-w-[720px] px-10 max-[760px]:px-[22px]';

export interface ThreadPaneProps {
  turns: TurnData[];
  canSubmit: boolean;
  onSubmit: (query: string) => void;
  activeCitationKey: string | null;
  onOpenCitation: (citation: CitationPayload) => void;
}

export function ThreadPane({
  turns,
  canSubmit,
  onSubmit,
  activeCitationKey,
  onOpenCitation,
}: ThreadPaneProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep the latest turn/stream in view.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

  const send = (value: string) => {
    const query = value.trim();
    if (!query || !canSubmit) return;
    onSubmit(query);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  return (
    <main className="relative flex min-h-0 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className={cx(readingColumn, 'pb-8 pt-20 max-[760px]:pt-12')}>
          {turns.length === 0 ? (
            <div className="max-w-[34rem]">
              <h1 className="font-display text-4xl font-medium leading-tight tracking-tight text-ink">
                Ask this codebase anything
              </h1>
              <p className="mt-3 font-display text-lg leading-relaxed text-ink-2">
                Every answer streams its reasoning and cites real, verified code you can open on the
                right.
              </p>
            </div>
          ) : (
            turns.map((turn) => (
              <Turn
                key={turn.id}
                turn={turn}
                activeCitationKey={activeCitationKey}
                onOpenCitation={onOpenCitation}
              />
            ))
          )}
        </div>
      </div>

      <div className="flex-none border-t border-line bg-[color-mix(in_srgb,var(--paper)_80%,transparent)] py-3.5 backdrop-blur-[8px]">
        <div className={readingColumn}>
          {turns.length === 0 && (
            <div className="flex flex-wrap gap-2 pb-2.5">
              {SUGGESTIONS.map((text) => (
                <button
                  key={text}
                  type="button"
                  disabled={!canSubmit}
                  onClick={() => send(text)}
                  className="rounded-full border border-line-2 bg-surface px-3 py-1.5 text-[12.5px] text-ink-2 transition hover:border-brand hover:bg-brand-wash hover:text-brand disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-line-2 disabled:hover:bg-surface disabled:hover:text-ink-2"
                >
                  {text}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2.5 rounded-[14px] border border-line-2 bg-surface p-2 pl-4 transition focus-within:border-brand focus-within:shadow-[0_0_0_3px_var(--brand-wash)]">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              disabled={!canSubmit}
              placeholder={canSubmit ? 'Ask a question about this repo…' : 'Select or index a repo to start'}
              spellCheck={false}
              onChange={(event) => {
                setInput(event.target.value);
                const el = event.target;
                el.style.height = 'auto';
                el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  send(input);
                }
              }}
              className="max-h-[120px] flex-1 resize-none bg-transparent py-2 font-sans text-[15px] leading-relaxed text-ink outline-none placeholder:text-ink-3 disabled:cursor-not-allowed"
            />
            <button
              type="button"
              aria-label="Send"
              disabled={!canSubmit || input.trim() === ''}
              onClick={() => send(input)}
              className="flex h-10 w-10 flex-none items-center justify-center rounded-[10px] bg-brand text-white transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40"
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
