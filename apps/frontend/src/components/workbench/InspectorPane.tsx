import type { CitationPayload } from '@/api/types';
import { VerifiedMark } from '@/components/ui';
import { cx } from '@/lib/cx';

export interface InspectorPaneProps {
  /** Open state of the right drawer below 1180px (ignored at wider widths). */
  open: boolean;
  onClose: () => void;
  citation: CitationPayload | null;
}

/**
 * Right code + call-graph inspector. Slice 3 shows the selected citation's
 * header (file:line + honest verified mark). Slice 5 fetches the real source
 * (Shiki-highlighted) + graph neighbors and fills the body.
 */
export function InspectorPane({ open, onClose, citation }: InspectorPaneProps) {
  return (
    <aside
      className={cx(
        'flex min-h-0 flex-col border-l border-line bg-surface',
        'max-[1180px]:fixed max-[1180px]:inset-y-0 max-[1180px]:right-0 max-[1180px]:z-50 max-[1180px]:w-[400px] max-[1180px]:max-w-[88vw] max-[1180px]:shadow-[-20px_0_50px_-30px_rgba(27,24,38,0.5)] max-[1180px]:transition-transform max-[1180px]:duration-300',
        open ? 'max-[1180px]:translate-x-0' : 'max-[1180px]:translate-x-full'
      )}
    >
      <div className="relative flex-none border-b border-line p-4">
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="absolute right-3 top-3 hidden h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition hover:bg-sunk max-[1180px]:flex"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
        </button>

        {citation ? (
          <>
            <div className="pr-8 font-mono text-[12.5px] font-medium text-ink">
              {citation.file_path}
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <span className="font-mono text-[11px] text-ink-2">
                {citation.symbol} · line {citation.line}
              </span>
              <VerifiedMark verified={citation.verified} />
            </div>
          </>
        ) : (
          <>
            <div className="font-mono text-[12.5px] font-medium text-ink">Inspector</div>
            <div className="mt-1.5 font-mono text-[11px] text-ink-3">click a citation to view source</div>
          </>
        )}
      </div>

      <div className="flex min-h-0 flex-1 items-center justify-center p-8 text-center">
        <p className="max-w-[16rem] text-sm leading-relaxed text-ink-3">
          {citation
            ? 'Real source + call-graph neighbors load here next (slice 5).'
            : 'Real source and call-graph neighbors appear here when you open a citation.'}
        </p>
      </div>
    </aside>
  );
}
