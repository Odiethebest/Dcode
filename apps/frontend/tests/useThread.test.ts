import { describe, expect, it } from 'vitest';

import type { QueryStreamEvent } from '@/api/types';
import { buildHistory, turnStatus, type Turn } from '@/hooks/useThread';

function turn(id: string, question: string, events: QueryStreamEvent[]): Turn {
  return { id, question, events, closed: true };
}

const finalAnswer: QueryStreamEvent = {
  event: 'final_answer',
  data: { answer: 'settled', citations: [], groundedness: 1 },
};
const citation: QueryStreamEvent = {
  event: 'citation',
  data: { symbol: 'X', file_path: 'a.py', line: 1, verified: true },
};
const partial: QueryStreamEvent = { event: 'partial_answer', data: { delta: 'draft' } };

describe('turnStatus', () => {
  it('is done ONLY when final_answer arrived', () => {
    expect(turnStatus({ id: 't', question: 'q', closed: true, events: [finalAnswer] })).toBe('done');
  });

  it('is interrupted — never done — when the stream closed without final_answer', () => {
    // The regression this pins: `closed` used to mean `done`, so an aborted turn
    // rendered its unredacted draft as the authoritative settled answer.
    expect(turnStatus({ id: 't', question: 'q', closed: true, events: [partial] })).toBe(
      'interrupted'
    );
    // Even with citations already flushed — they arrive just before final_answer,
    // so this window is real, and they still must not count as a settled turn.
    expect(turnStatus({ id: 't', question: 'q', closed: true, events: [partial, citation] })).toBe(
      'interrupted'
    );
    // An empty aborted turn is interrupted too, not done.
    expect(turnStatus({ id: 't', question: 'q', closed: true, events: [] })).toBe('interrupted');
  });

  it('is streaming while open, and error wins over everything', () => {
    expect(turnStatus({ id: 't', question: 'q', closed: false, events: [partial] })).toBe(
      'streaming'
    );
    expect(
      turnStatus({
        id: 't',
        question: 'q',
        closed: true,
        events: [finalAnswer, { event: 'error', data: { code: 'X', message: 'boom' } }],
      })
    ).toBe('error');
  });
});

describe('buildHistory (multi-turn context)', () => {
  it('emits a user/assistant pair per completed turn, skipping errored/streaming ones', () => {
    const turns: Turn[] = [
      turn('turn-1', 'where is HTTPBasicAuth?', [
        {
          event: 'final_answer',
          data: { answer: 'In `src/requests/auth.py:85`.', citations: [], groundedness: 1 },
        },
      ]),
      turn('turn-2', 'and its callers?', [{ event: 'error', data: { code: 'X', message: 'boom' } }]),
      turn('turn-3', 'still going', [{ event: 'partial_answer', data: { delta: 'thinking' } }]),
    ];

    expect(buildHistory(turns)).toEqual([
      { role: 'user', content: 'where is HTTPBasicAuth?' },
      { role: 'assistant', content: 'In `src/requests/auth.py:85`.' },
    ]);
  });

  it('is empty for a fresh thread', () => {
    expect(buildHistory([])).toEqual([]);
  });

  it('never feeds an interrupted turn back as context', () => {
    // An interrupted turn's draft was never redacted by groundedness. Sending it
    // as assistant context would let unverifiable references re-enter the loop.
    const interrupted: Turn = {
      id: 'turn-1',
      question: 'where is HTTPBasicAuth?',
      closed: true,
      stopped: true,
      events: [partial, citation],
    };
    expect(buildHistory([interrupted])).toEqual([]);
  });
});
