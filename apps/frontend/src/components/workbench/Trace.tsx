import { useState, type ReactNode } from 'react';

import type { QueryStreamEvent } from '@/api/types';
import type { TurnStatus } from '@/hooks/useThread';
import { cx } from '@/lib/cx';

const TRACE_KINDS = new Set(['thought', 'tool_call', 'tool_result']);

const pillTone: Record<TurnStatus, string> = {
  // Neutral while running — NOT green — so nothing reads as "grounded" until settle.
  streaming: 'bg-sunk text-ink-2',
  done: 'bg-good-wash text-good',
  error: 'bg-bad-wash text-bad',
};

function argsSummary(args: Record<string, unknown>): string {
  const rendered = Object.entries(args)
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
    .join(', ');
  return rendered.length > 90 ? `${rendered.slice(0, 90)}…` : rendered;
}

function TraceRow({ event }: { event: QueryStreamEvent }) {
  let knob = 'bg-ink-3';
  let kind = '';
  let body: ReactNode = null;
  if (event.event === 'thought') {
    knob = 'bg-brand';
    kind = 'Thought';
    body = event.data.content;
  } else if (event.event === 'tool_call') {
    knob = 'bg-ink-2';
    kind = event.data.tool;
    body = <span className="font-mono text-[11.5px] text-ink-2">{argsSummary(event.data.args)}</span>;
  } else if (event.event === 'tool_result') {
    knob = 'bg-ink-2';
    kind = event.data.tool;
    body = event.data.result_summary;
  }
  return (
    <div className="flex gap-2.5">
      <span className={cx('mt-1.5 h-2 w-2 flex-none rounded-full', knob)} aria-hidden="true" />
      <div className="min-w-0">
        <div className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-ink-3">{kind}</div>
        <div className="mt-0.5 text-[13px] leading-snug text-ink">{body}</div>
      </div>
    </div>
  );
}

export interface TraceProps {
  events: QueryStreamEvent[];
  status: TurnStatus;
  groundedness: number | null;
  toolCount: number;
}

export function Trace({ events, status, groundedness, toolCount }: TraceProps) {
  const [open, setOpen] = useState(false);
  const traceEvents = events.filter((event) => TRACE_KINDS.has(event.event));

  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cx(
          'inline-flex items-center gap-2.5 rounded-full px-3 py-[5px] font-mono text-[11.5px] transition',
          pillTone[status]
        )}
      >
        {status === 'done' && groundedness != null ? (
          <>
            <svg viewBox="0 0 12 12" fill="none" className="h-3 w-3" aria-hidden="true">
              <path d="M2.5 6.2l2.2 2.3 4.8-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            grounded {groundedness.toFixed(2)}
            <span className="border-l border-line-2 pl-2.5 text-ink-2">{toolCount} tools</span>
          </>
        ) : status === 'error' ? (
          <>trace</>
        ) : (
          <>
            <span className="h-2 w-2 animate-pulse rounded-full bg-ink-3 motion-reduce:animate-none" aria-hidden="true" />
            reasoning…
            {toolCount > 0 && <span className="border-l border-line-2 pl-2.5">{toolCount} tools</span>}
          </>
        )}
        {traceEvents.length > 0 && (
          <svg
            viewBox="0 0 12 12"
            fill="none"
            className={cx('h-3 w-3 transition-transform', open && 'rotate-90')}
            aria-hidden="true"
          >
            <path d="M4 2.5l3.5 3.5L4 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>

      {open && traceEvents.length > 0 && (
        <div className="mt-2 space-y-3 rounded-xl border border-line bg-surface p-4">
          {traceEvents.map((event, index) => (
            <TraceRow key={index} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
