import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { getNeighbors, getSource } from '@/api/client';
import type { CitationPayload, Location, SymbolNeighbors } from '@/api/types';
import { VerifiedMark } from '@/components/ui';
import { SourceView } from '@/components/workbench/SourceView';
import { cx } from '@/lib/cx';

interface Focus {
  symbol: string;
  file_path: string;
  line: number;
}

export interface InspectorPaneProps {
  /** Open state of the right drawer below 1180px (ignored at wider widths). */
  open: boolean;
  onClose: () => void;
  repoId: string | null;
  citation: CitationPayload | null;
}

/**
 * Right code + call-graph inspector — the signature. A cited file:line (or a
 * walked-to graph node) fetches real source (Shiki-highlighted, cited line
 * marked) + call-graph neighbors; clicking a neighbor walks the graph.
 */
export function InspectorPane({ open, onClose, repoId, citation }: InspectorPaneProps) {
  const [focus, setFocus] = useState<Focus | null>(null);

  // A thread citation click (or clearing it on repo change) drives the focus;
  // neighbor clicks then move it locally without touching the thread.
  useEffect(() => {
    setFocus(
      citation
        ? { symbol: citation.symbol, file_path: citation.file_path, line: citation.line }
        : null
    );
  }, [citation]);

  const source = useQuery({
    queryKey: ['source', repoId, focus?.file_path, focus?.line, focus?.symbol],
    queryFn: () =>
      getSource(repoId as string, {
        file_path: focus?.file_path,
        line: focus?.line,
        symbol: focus?.symbol,
      }),
    enabled: Boolean(repoId && focus),
  });

  const neighbors = useQuery({
    queryKey: ['neighbors', repoId, focus?.symbol],
    queryFn: () => getNeighbors(repoId as string, focus?.symbol as string),
    enabled: Boolean(repoId && focus?.symbol),
  });

  const atCitation =
    citation != null &&
    focus != null &&
    focus.symbol === citation.symbol &&
    focus.file_path === citation.file_path &&
    focus.line === citation.line;

  const walkTo = (loc: Location) =>
    setFocus({ symbol: loc.symbol, file_path: loc.file_path, line: loc.line });

  const src = source.data;

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

        {focus ? (
          <>
            <div className="pr-8 font-mono text-[12.5px] font-medium text-ink">
              {src?.file_path ?? focus.file_path}
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <span className="font-mono text-[11px] text-ink-2">
                {src?.symbol_name ?? focus.symbol} · line {src?.cited_line ?? focus.line}
              </span>
              {atCitation && citation && <VerifiedMark verified={citation.verified} />}
            </div>
          </>
        ) : (
          <>
            <div className="font-mono text-[12.5px] font-medium text-ink">Inspector</div>
            <div className="mt-1.5 font-mono text-[11px] text-ink-3">click a citation to view source</div>
          </>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!focus ? (
          <div className="flex h-full items-center justify-center p-8 text-center">
            <p className="max-w-[16rem] text-sm leading-relaxed text-ink-3">
              Real source and call-graph neighbors appear here when you open a citation.
            </p>
          </div>
        ) : source.isPending || neighbors.isPending ? (
          <p className="p-6 font-mono text-[11px] text-ink-3">loading source…</p>
        ) : source.isError ? (
          <p className="p-6 text-sm text-bad">Couldn’t load source for this reference.</p>
        ) : (
          <>
            {src?.found && src.content ? (
              <SourceView
                content={src.content}
                startLine={src.start_line ?? focus.line}
                citedLine={src.cited_line}
              />
            ) : src?.granularity === 'file_outline' ? (
              <div className="p-4">
                <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">
                  file outline · source not indexed at this line
                </div>
                <div className="space-y-1">
                  {src.outline.map((loc) => (
                    <button
                      key={`${loc.symbol}:${loc.line}`}
                      type="button"
                      onClick={() => walkTo(loc)}
                      className="block w-full rounded-md px-2 py-1.5 text-left font-mono text-[12px] text-ink transition hover:bg-sunk"
                    >
                      {loc.symbol} · line {loc.line}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <p className="p-6 text-sm text-ink-3">
                Source isn’t indexed at this granularity.
              </p>
            )}

            {neighbors.data?.found && <CallGraph neighbors={neighbors.data} onWalk={walkTo} />}
          </>
        )}
      </div>
    </aside>
  );
}

function CallGraph({
  neighbors,
  onWalk,
}: {
  neighbors: SymbolNeighbors;
  onWalk: (loc: Location) => void;
}) {
  const groups: Array<[string, Location[]]> = [
    ['Called by', neighbors.called_by],
    ['Calls', neighbors.calls],
    ['References', neighbors.references],
  ];
  if (groups.every(([, list]) => list.length === 0)) return null;

  return (
    <div className="border-t border-line p-[18px]">
      <h4 className="mb-3 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">
        In the call graph
      </h4>
      {groups.map(([label, list]) =>
        list.length === 0 ? null : (
          <div key={label} className="mb-5 last:mb-0">
            <div className="mb-2 font-mono text-[11px] text-ink-2">{label}</div>
            {list.map((loc) => (
              <button
                key={`${loc.symbol}:${loc.file_path}:${loc.line}`}
                type="button"
                onClick={() => onWalk(loc)}
                className="mb-1.5 flex w-full items-center justify-between gap-2.5 rounded-[9px] border border-line px-3 py-2.5 text-left transition last:mb-0 hover:border-brand hover:bg-brand-wash"
              >
                <span className="truncate font-mono text-[12px] text-brand">{loc.symbol}</span>
                <span className="flex-none font-mono text-[10.5px] text-ink-3">
                  {loc.file_path.split('/').pop()}:{loc.line}
                </span>
              </button>
            ))}
          </div>
        )
      )}
    </div>
  );
}
