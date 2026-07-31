import type { ReactNode } from 'react';
import Markdown, { type Components } from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import 'katex/dist/katex.min.css';

import type { CitationPayload } from '@/api/types';
import { CitationChip, CodeChip } from '@/components/ui';
import { citationKey, findCitationForToken } from '@/lib/citations';
import { cx } from '@/lib/cx';

export interface AnswerMarkdownProps {
  text: string;
  /** Empty while streaming — chips/verified marks bind only once these arrive. */
  citations: CitationPayload[];
  activeKey: string | null;
  onOpenCitation: (citation: CitationPayload) => void;
  /**
   * Demote the prose off the settled-answer voice (interrupted drafts). A real
   * prop rather than a `className` override: two same-specificity Tailwind text
   * colors would resolve by stylesheet order, not by class-attribute order.
   */
  muted?: boolean;
}

interface Fence {
  marker: '`' | '~';
  length: number;
}

function normalizeKatexExpression(expression: string): string {
  // A frequent model slip is `\text{BM25_score}`. In TeX text mode the
  // underscore still needs escaping; repair only this narrow, unambiguous case
  // and let KaTeX surface every other syntax error honestly.
  return expression.replace(/\\text\{([^{}]*)\}/g, (_match, content: string) => {
    const escaped = content.replace(/(^|[^\\])_/g, '$1\\_');
    return `\\text{${escaped}}`;
  });
}

/**
 * Models commonly emit LaTeX's `\\(...\\)` / `\\[...\\]` delimiters, while
 * remark-math intentionally parses Markdown's `$...$` / `$$...$$` syntax.
 * Normalize the former before Markdown parsing, without touching examples
 * inside inline code or fenced code blocks.
 */
export function normalizeMathDelimiters(markdown: string): string {
  let output = '';
  let index = 0;
  let fence: Fence | null = null;

  while (index < markdown.length) {
    const atLineStart = index === 0 || markdown[index - 1] === '\n';
    if (atLineStart) {
      const lineEndIndex = markdown.indexOf('\n', index);
      const lineEnd = lineEndIndex === -1 ? markdown.length : lineEndIndex + 1;
      const line = markdown.slice(index, lineEnd);
      const fenceMatch = /^ {0,3}(`{3,}|~{3,})/.exec(line);
      if (fenceMatch) {
        const run = fenceMatch[1];
        const marker = run[0] as Fence['marker'];
        if (fence === null) {
          fence = { marker, length: run.length };
        } else if (marker === fence.marker && run.length >= fence.length) {
          fence = null;
        }
        output += line;
        index = lineEnd;
        continue;
      }
    }

    if (fence !== null) {
      output += markdown[index];
      index += 1;
      continue;
    }

    if (markdown[index] === '`') {
      let runEnd = index + 1;
      while (markdown[runEnd] === '`') runEnd += 1;
      const marker = markdown.slice(index, runEnd);
      const closing = markdown.indexOf(marker, runEnd);
      if (closing !== -1) {
        const segmentEnd = closing + marker.length;
        output += markdown.slice(index, segmentEnd);
        index = segmentEnd;
        continue;
      }
    }

    if (markdown.startsWith('\\[', index)) {
      const closing = markdown.indexOf('\\]', index + 2);
      if (closing !== -1) {
        const expression = normalizeKatexExpression(markdown.slice(index + 2, closing).trim());
        output += `\n\n$$\n${expression}\n$$\n\n`;
        index = closing + 2;
        continue;
      }
    }

    if (markdown.startsWith('\\(', index)) {
      const closing = markdown.indexOf('\\)', index + 2);
      if (closing !== -1) {
        const expression = normalizeKatexExpression(markdown.slice(index + 2, closing));
        output += `$${expression}$`;
        index = closing + 2;
        continue;
      }
    }

    output += markdown[index];
    index += 1;
  }

  return output;
}

/**
 * Sanitized markdown → React elements (no dangerouslySetInnerHTML, no
 * rehype-raw), with KaTeX generated from math nodes only. Inline code that
 * matches a citation renders a clickable CitationChip; an inline ref with no
 * citation renders an inert CodeChip (never a dead citation chip).
 */
export function AnswerMarkdown({
  text,
  citations,
  activeKey,
  onOpenCitation,
  muted = false,
}: AnswerMarkdownProps) {
  const components: Components = {
    code({ className, children }) {
      const token = String(children).replace(/\n$/, '');
      const isBlock = Boolean(className?.includes('language-')) || token.includes('\n');
      if (isBlock) {
        return <code className="font-mono text-[12.5px]">{children}</code>;
      }
      const citation = findCitationForToken(token, citations);
      if (citation) {
        return (
          <CitationChip
            verified={citation.verified}
            active={activeKey === citationKey(citation)}
            onClick={() => onOpenCitation(citation)}
          >
            {token}
          </CitationChip>
        );
      }
      return <CodeChip>{token}</CodeChip>;
    },
    pre({ children }: { children?: ReactNode }) {
      return (
        <pre className="my-3 overflow-x-auto rounded-md bg-sunk-2 p-3 font-mono text-[12.5px] leading-relaxed text-ink">
          {children}
        </pre>
      );
    },
    a({ href, children }) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="text-brand underline underline-offset-2"
        >
          {children}
        </a>
      );
    },
  };

  return (
    <div
      className={cx(
        'font-display text-[18px] leading-[1.62] [&_.katex-display]:my-4 [&_.katex-display]:overflow-x-auto [&_.katex-display]:overflow-y-hidden [&_li]:mb-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-3.5 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5',
        muted ? 'text-ink-2' : 'text-ink'
      )}
    >
      <Markdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {normalizeMathDelimiters(text)}
      </Markdown>
    </div>
  );
}
