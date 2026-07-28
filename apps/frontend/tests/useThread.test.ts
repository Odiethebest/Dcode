import { describe, expect, it } from 'vitest';

import type { QueryStreamEvent } from '@/api/types';
import { buildHistory, type Turn } from '@/hooks/useThread';

function turn(id: string, question: string, events: QueryStreamEvent[]): Turn {
  return { id, question, events, closed: true };
}

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
});
