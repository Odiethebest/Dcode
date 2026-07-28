import { describe, expect, it } from 'vitest';

import type { CitationPayload } from '@/api/types';
import { findCitationForToken, tokenMatchesCitation, unmatchedCitations } from '@/lib/citations';

const authCall: CitationPayload = {
  symbol: 'HTTPBasicAuth.__call__',
  file_path: 'src/requests/auth.py',
  line: 85,
  verified: true,
};
const prepare: CitationPayload = {
  symbol: 'PreparedRequest.prepare_auth',
  file_path: 'src/requests/models.py',
  line: 471,
  verified: true,
};

describe('citation matching', () => {
  it('matches a file:line token to its citation', () => {
    expect(tokenMatchesCitation('src/requests/auth.py:85', authCall)).toBe(true);
    expect(tokenMatchesCitation('src/requests/auth.py:86', authCall)).toBe(false);
  });

  it('matches a qualified-symbol token to its citation', () => {
    expect(tokenMatchesCitation('PreparedRequest.prepare_auth', prepare)).toBe(true);
  });

  it('finds the citation for a token, or none', () => {
    expect(findCitationForToken('src/requests/models.py:471', [authCall, prepare])).toBe(prepare);
    expect(findCitationForToken('nope.py:1', [authCall, prepare])).toBeUndefined();
  });

  it('reports citations not referenced inline as unmatched (the Sources footer)', () => {
    const text = 'The header is set in `src/requests/auth.py:85`.';
    expect(unmatchedCitations(text, [authCall, prepare])).toEqual([prepare]);
  });
});
