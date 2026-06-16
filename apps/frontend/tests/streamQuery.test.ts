import { describe, expect, it, vi, afterEach } from 'vitest';

import { streamQuery } from '@/api/client';
import type { QueryStreamEvent } from '@/api/types';

function makeStream(chunks: string[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(new TextEncoder().encode(chunk));
      }
      controller.close();
    },
  });
}

describe('streamQuery', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('parses chunked SSE events in order', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          makeStream([
            'event: thought\n',
            'data: {"step":1,"content":"route"}\n\n',
            'event: final_answer\n',
            'data: {"answer":"done","citations":[],"groundedness":1.0}\n\n',
          ]),
          { status: 200 }
        )
      )
    );

    const events: QueryStreamEvent[] = [];
    await streamQuery(
      { repo_id: 'repo-1', query: 'Where is X?' },
      (event) => events.push(event)
    );

    expect(events).toEqual([
      { event: 'thought', data: { step: 1, content: 'route' } },
      {
        event: 'final_answer',
        data: { answer: 'done', citations: [], groundedness: 1.0 },
      },
    ]);
  });

  it('surfaces non-200 query failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('boom', { status: 502 }))
    );

    await expect(
      streamQuery({ repo_id: 'repo-1', query: 'Where is X?' }, () => {})
    ).rejects.toThrow('POST /api/v1/query failed: 502 boom');
  });
});
