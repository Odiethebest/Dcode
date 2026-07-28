import { useCallback, useEffect, useRef, useState } from 'react';

import { streamQuery } from '@/api/client';
import type { QueryStreamEvent } from '@/api/types';

export interface Turn {
  id: string;
  question: string;
  events: QueryStreamEvent[];
  closed: boolean;
}

export type TurnStatus = 'streaming' | 'done' | 'error';

/**
 * A turn's phase is derived purely from which events have arrived — never a
 * timer. `error` if the stream errored; `done` once `final_answer` lands (or
 * the stream closed); otherwise `streaming`. This is what keeps verified
 * marks + groundedness off-screen until end-of-run.
 */
export function turnStatus(turn: Turn): TurnStatus {
  if (turn.events.some((event) => event.event === 'error')) return 'error';
  if (turn.events.some((event) => event.event === 'final_answer')) return 'done';
  return turn.closed ? 'done' : 'streaming';
}

let turnSeq = 0;

export interface UseThread {
  turns: Turn[];
  isStreaming: boolean;
  submit: (query: string) => void;
}

/** Repo-scoped conversation state driving the SSE thread. */
export function useThread(repoId: string | null): UseThread {
  const [turns, setTurns] = useState<Turn[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  // The thread is scoped to one repo — reset when it changes.
  useEffect(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setTurns([]);
  }, [repoId]);

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  const patch = useCallback((id: string, fn: (turn: Turn) => Turn) => {
    setTurns((current) => current.map((turn) => (turn.id === id ? fn(turn) : turn)));
  }, []);

  const submit = useCallback(
    (raw: string) => {
      const query = raw.trim();
      if (!query || !repoId) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const id = `turn-${++turnSeq}`;
      setTurns((current) => [...current, { id, question: query, events: [], closed: false }]);

      void streamQuery(
        { repo_id: repoId, query },
        (event) => patch(id, (turn) => ({ ...turn, events: [...turn.events, event] })),
        controller.signal
      )
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          const message = error instanceof Error ? error.message : 'stream failed';
          patch(id, (turn) => ({
            ...turn,
            events: [...turn.events, { event: 'error', data: { code: 'STREAM_ERROR', message } }],
          }));
        })
        .finally(() => {
          patch(id, (turn) => ({ ...turn, closed: true }));
          if (abortRef.current === controller) abortRef.current = null;
        });
    },
    [repoId, patch]
  );

  const isStreaming = turns.some((turn) => turnStatus(turn) === 'streaming');
  return { turns, isStreaming, submit };
}
