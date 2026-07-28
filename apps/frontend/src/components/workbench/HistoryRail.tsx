import { cx } from '@/lib/cx';

export interface HistoryRailProps {
  /** Open state of the left drawer below 760px (ignored at wider widths). */
  open: boolean;
}

/**
 * Left history rail. Below 760px it becomes a slide-in drawer; at wider widths
 * it's the first grid column. The thread list is a placeholder here — real
 * conversation history lands in slice 3/4.
 */
export function HistoryRail({ open }: HistoryRailProps) {
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
          className="flex w-full items-center justify-center gap-2 rounded-[10px] bg-brand px-3 py-2.5 text-sm font-semibold text-white shadow-[0_1px_0_rgba(27,24,38,0.18)] transition hover:bg-brand-hover"
        >
          + New question
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2.5 pb-4">
        <p className="px-2 py-10 text-center text-sm text-ink-3">
          No questions yet. Ask one below to start a thread.
        </p>
      </div>
    </aside>
  );
}
