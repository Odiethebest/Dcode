import { useEffect, useState } from 'react';

import { highlightPython, type Tok } from '@/lib/highlight';
import { cx } from '@/lib/cx';

export interface SourceViewProps {
  content: string;
  startLine: number;
  citedLine: number | null;
}

/**
 * Renders a source chunk with line numbers and a highlighted cited line. Shiki
 * (Python, Dcode theme) colors it once loaded; until then / on failure it shows
 * plain text so numbering + the cited-line marker always work.
 */
export function SourceView({ content, startLine, citedLine }: SourceViewProps) {
  const [highlighted, setHighlighted] = useState<Tok[][] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setHighlighted(null);
    void highlightPython(content).then((result) => {
      if (!cancelled) setHighlighted(result);
    });
    return () => {
      cancelled = true;
    };
  }, [content]);

  const plain: Tok[][] = content.replace(/\n$/, '').split('\n').map((line) => [{ content: line }]);
  const lines = highlighted ?? plain;

  return (
    <div className="overflow-x-auto bg-sunk-2 py-3.5 font-mono text-[12.5px] leading-[1.62]">
      {lines.map((tokens, index) => {
        const lineNo = startLine + index;
        const cited = citedLine != null && lineNo === citedLine;
        return (
          <div
            key={index}
            className={cx(
              'flex whitespace-pre px-4',
              cited && 'bg-brand-wash shadow-[inset_3px_0_0_var(--brand)]'
            )}
          >
            <span
              className={cx(
                'w-9 flex-none select-none pr-4 text-right',
                cited ? 'text-brand' : 'text-ink-3 opacity-75'
              )}
            >
              {lineNo}
            </span>
            <span className="text-ink">
              {tokens.map((token, tokenIndex) => (
                <span
                  key={tokenIndex}
                  style={{
                    color: token.color,
                    fontWeight: token.bold ? 600 : undefined,
                    fontStyle: token.italic ? 'italic' : undefined,
                  }}
                >
                  {token.content}
                </span>
              ))}
            </span>
          </div>
        );
      })}
    </div>
  );
}
