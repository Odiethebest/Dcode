import type { ReactNode } from 'react';
import Markdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

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

/**
 * Sanitized markdown → React elements (no dangerouslySetInnerHTML, no
 * rehype-raw), fixing the old literal-`**` bug. Inline code that matches a
 * citation renders a clickable CitationChip; an inline ref with no citation
 * renders an inert CodeChip (never a dead citation chip).
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
        'font-display text-[18px] leading-[1.62] [&_li]:mb-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-3.5 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5',
        muted ? 'text-ink-2' : 'text-ink'
      )}
    >
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </Markdown>
    </div>
  );
}
