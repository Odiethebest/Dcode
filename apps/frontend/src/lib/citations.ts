import type { CitationPayload, FinalAnswerPayload, QueryStreamEvent } from '@/api/types';

/** Stable identity for a citation — the merge/match key. */
export function citationKey(citation: CitationPayload): string {
  return `${citation.symbol}|${citation.file_path}|${citation.line}`;
}

/**
 * Merge streamed `citation` events with `final_answer.citations`, de-duped by
 * key. (Today both arrive together at end-of-run; the merge keeps the reserved
 * support for future mid-run citations.)
 */
export function mergeCitations(
  events: QueryStreamEvent[],
  finalAnswer: FinalAnswerPayload | undefined
): CitationPayload[] {
  const merged = new Map<string, CitationPayload>();
  for (const event of events) {
    if (event.event === 'citation') merged.set(citationKey(event.data), event.data);
  }
  for (const citation of finalAnswer?.citations ?? []) {
    merged.set(citationKey(citation), citation);
  }
  return [...merged.values()];
}

const FILE_LINE = /^([\w./-]+\.py):(\d+)$/;

/** Does a backticked inline-code token refer to this citation? */
export function tokenMatchesCitation(token: string, citation: CitationPayload): boolean {
  const trimmed = token.trim();
  const fileLine = FILE_LINE.exec(trimmed);
  if (fileLine) {
    return citation.file_path === fileLine[1] && citation.line === Number(fileLine[2]);
  }
  return citation.symbol === trimmed;
}

export function findCitationForToken(
  token: string,
  citations: CitationPayload[]
): CitationPayload | undefined {
  return citations.find((citation) => tokenMatchesCitation(token, citation));
}

/** The `...`-delimited inline-code tokens in a markdown string. */
export function inlineCodeTokens(text: string): string[] {
  return [...text.matchAll(/`([^`\n]+)`/g)].map((match) => match[1]);
}

/** Verified citations NOT referenced inline in the answer → the Sources footer. */
export function unmatchedCitations(
  text: string,
  citations: CitationPayload[]
): CitationPayload[] {
  const tokens = inlineCodeTokens(text);
  return citations.filter(
    (citation) => !tokens.some((token) => tokenMatchesCitation(token, citation))
  );
}
