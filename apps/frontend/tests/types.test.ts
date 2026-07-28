import { describe, expect, it } from 'vitest';

import type { QueryRequest, QueryTurn, RepoStatusResponse } from '@/api/types';

/**
 * Manual-mirror guardrail. types.ts is hand-synced to the Python
 * `dcode_shared.schemas` (no openapi-typescript yet), and it has drifted before
 * (RepoStatusResponse.url). These object literals are typed, so if the mirror
 * loses `history` / the QueryTurn role+content pair, or `url` again, this file
 * stops compiling under `npm run typecheck` and the build fails. The runtime
 * asserts document the expected shape.
 */

describe('QueryRequest history mirrors QueryTurn', () => {
  it('carries typed role/content turns and keeps history optional', () => {
    const turn: QueryTurn = { role: 'user', content: 'explain HTTPBasicAuth' };
    const followUp: QueryRequest = {
      repo_id: 'repo-1',
      query: 'who calls it?',
      history: [turn, { role: 'assistant', content: 'It attaches an Authorization header.' }],
    };

    expect(Object.keys(turn).sort()).toEqual(['content', 'role']);
    expect(followUp.history?.[0].role).toBe('user');

    // Single-turn requests omit history (the field is optional).
    const singleTurn: QueryRequest = { repo_id: 'repo-1', query: 'where is X?' };
    expect(singleTurn.history).toBeUndefined();
  });
});

describe('RepoStatusResponse mirrors the backend url field', () => {
  it('includes url (drift regression)', () => {
    const status: RepoStatusResponse = {
      repo_id: 'repo-1',
      url: 'https://github.com/psf/requests.git',
      status: 'ready',
      progress: 100,
      stages: { cloning: 'done', parsing: 'done', embedding: 'done', graphing: 'done' },
      error: null,
      warnings: [],
    };

    expect(status.url).toContain('requests');
  });
});
