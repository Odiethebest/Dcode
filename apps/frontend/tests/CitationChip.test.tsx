import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { describe, expect, it } from 'vitest';

import { CitationChip } from '@/components/ui';

function classesOf(ui: ReactElement): string {
  const { container } = render(ui);
  return container.querySelector('button')?.className ?? '';
}

// The honesty rule: solid/filled emphasis is reserved for verified/active. An
// unverified citation must never out-emphasize a verified one.
describe('CitationChip honesty rule', () => {
  it('renders unverified chips as amber outline + pale fill, never solid', () => {
    for (const active of [false, true]) {
      const cls = classesOf(
        <CitationChip verified={false} active={active}>
          x.py:1
        </CitationChip>
      );
      expect(cls).toContain('bg-warn-wash'); // pale-amber fill
      expect(cls).toContain('border-warn'); // amber outline
      expect(cls).not.toMatch(/bg-warn(?![-\w])/); // never the solid amber fill
      expect(cls).not.toContain('text-white'); // never inverted
    }
  });

  it('reserves solid fill for verified-active only', () => {
    const cls = classesOf(
      <CitationChip verified active>
        x.py:1
      </CitationChip>
    );
    expect(cls).toContain('bg-brand');
    expect(cls).toContain('text-white');
  });
});
