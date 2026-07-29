import type { ReactNode } from 'react';

import { cx } from '@/lib/cx';

export interface CodeChipProps {
  children: ReactNode;
  className?: string;
}

/** Inline mono code token — the machine-evidence voice inside prose. */
export function CodeChip({ children, className }: CodeChipProps) {
  return (
    <code
      className={cx(
        'whitespace-nowrap rounded-md bg-sunk px-1.5 py-[1.5px] font-mono text-[0.8em] text-ink',
        className
      )}
    >
      {children}
    </code>
  );
}
