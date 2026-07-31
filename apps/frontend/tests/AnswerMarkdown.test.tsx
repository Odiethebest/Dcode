import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AnswerMarkdown, normalizeMathDelimiters } from '@/components/workbench/AnswerMarkdown';

const baseProps = {
  citations: [],
  activeKey: null,
  onOpenCitation: () => {},
};

describe('AnswerMarkdown math', () => {
  it('renders inline and display LaTeX, including model-style bracket delimiters', () => {
    const text = String.raw`Inline: \(\alpha + \beta\).

\[
\text{score} = \alpha_{\text{keyword}} \times \text{BM25_score}
    \]`;
    const { container } = render(<AnswerMarkdown {...baseProps} text={text} />);

    expect(container.querySelectorAll('.katex')).toHaveLength(2);
    expect(container.querySelectorAll('.katex-display')).toHaveLength(1);
    expect(container.querySelector('.katex-error')).toBeNull();
    expect(container.textContent).toContain('score');
  });

  it('does not reinterpret LaTeX delimiters inside code', () => {
    const text = ['Inline code: `\\(\\alpha\\)`', '', '```text', '\\[\\beta\\]', '```'].join('\n');
    const { container } = render(<AnswerMarkdown {...baseProps} text={text} />);

    expect(container.querySelector('.katex')).toBeNull();
    expect(container.textContent).toContain(String.raw`\(\alpha\)`);
    expect(container.textContent).toContain(String.raw`\[\beta\]`);
  });

  it('leaves an incomplete streamed delimiter untouched until it closes', () => {
    expect(normalizeMathDelimiters(String.raw`Working on \(\alpha`)).toBe(
      String.raw`Working on \(\alpha`
    );
  });
});
