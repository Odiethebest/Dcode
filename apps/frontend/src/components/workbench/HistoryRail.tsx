import type { QueryStreamEvent } from '@/api/types';
import { turnStatus, type Turn } from '@/hooks/useThread';
import { mergeCitations } from '@/lib/citations';
import { cx } from '@/lib/cx';

function itemMeta(turn: Turn): string {
  const status = turnStatus(turn);
  if (status === 'streaming') return 'answering…';
  if (status === 'error') return 'error';
  // No citation count for an interrupted turn — none of them ever bound.
  if (status === 'interrupted') return 'interrupted';
  const final = turn.events.find(
    (event): event is Extract<QueryStreamEvent, { event: 'final_answer' }> =>
      event.event === 'final_answer'
  );
  const count = mergeCitations(turn.events, final?.data).length;
  const cites = `${count} citation${count === 1 ? '' : 's'}`;
  const grounded = final?.data.groundedness;
  return grounded != null ? `grounded ${grounded.toFixed(2)} · ${cites}` : cites;
}

export interface HistoryRailProps {
  /** Open state of the left drawer below 760px (ignored at wider widths). */
  open: boolean;
  turns: Turn[];
  /** Close the mobile drawer after a jump. */
  onNavigate: () => void;
}

/**
 * Left history rail — the questions in this (repo-scoped) thread. Tapping one
 * scrolls the thread to that turn; "New question" jumps to the composer. Both
 * close the mobile drawer.
 */
export function HistoryRail({ open, turns, onNavigate }: HistoryRailProps) {
  const goToTurn = (id: string) => {
    // scrollIntoView is a no-op under jsdom — optional-call so tests don't throw.
    document.getElementById(id)?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    onNavigate();
  };

  const newQuestion = () => {
    const input = document.getElementById('workbench-input');
    input?.scrollIntoView?.({ block: 'center' });
    (input as HTMLTextAreaElement | null)?.focus();
    onNavigate();
  };

  return (
    <aside
      className={cx(
        'flex min-h-0 flex-col border-r border-line bg-[color-mix(in_srgb,var(--paper)_60%,var(--surface))]',
        'max-[760px]:fixed max-[760px]:inset-y-0 max-[760px]:left-0 max-[760px]:z-50 max-[760px]:w-[280px] max-[760px]:max-w-[84vw] max-[760px]:shadow-[20px_0_50px_-30px_rgba(27,24,38,0.5)] max-[760px]:transition-transform max-[760px]:duration-300',
        open ? 'max-[760px]:translate-x-0' : 'max-[760px]:-translate-x-full'
      )}
    >
      <div className="p-4">
        <button
          type="button"
          onClick={newQuestion}
          className="flex w-full items-center justify-center gap-2 rounded-[10px] bg-brand px-3 py-2.5 text-sm font-semibold text-white shadow-[0_1px_0_rgba(27,24,38,0.18)] transition hover:bg-brand-hover"
        >
          + New question
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2.5 pb-4">
        {turns.length === 0 ? (
          <p className="px-2 py-10 text-center text-sm text-ink-3">
            No questions yet. Ask one below to start a thread.
          </p>
        ) : (
          <div className="space-y-1">
            {turns.map((turn) => (
              <button
                key={turn.id}
                type="button"
                onClick={() => goToTurn(turn.id)}
                className="block w-full rounded-[9px] px-2.5 py-2.5 text-left transition hover:bg-sunk"
              >
                <span className="line-clamp-2 font-display text-[14.5px] leading-snug text-ink">
                  {turn.question}
                </span>
                <span className="mt-1 block font-mono text-[10.5px] text-ink-3">{itemMeta(turn)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
