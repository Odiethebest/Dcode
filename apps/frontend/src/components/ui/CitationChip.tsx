import type { ReactNode } from 'react';

import { cx } from '@/lib/cx';

const tones = {
  verified: {
    idle: 'bg-brand-wash text-brand hover:border-brand',
    active: 'bg-brand text-white',
  },
  unverified: {
    idle: 'bg-warn-wash text-warn hover:border-warn',
    active: 'bg-warn text-white',
  },
};

export interface CitationChipProps {
  children: ReactNode;
  active?: boolean;
  verified?: boolean;
  onClick?: () => void;
  className?: string;
}

/**
 * Clickable inline citation (⟦file:line⟧). Opens the inspector on click and
 * marks itself active. `verified: false` shifts off the brand hue to amber so an
 * unverified reference never masquerades as a grounded one.
 */
export function CitationChip({
  children,
  active = false,
  verified = true,
  onClick,
  className,
}: CitationChipProps) {
  const tone = verified ? tones.verified : tones.unverified;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cx(
        'inline-flex items-center whitespace-nowrap rounded-md border border-transparent px-[7px] py-0.5 align-[1px] font-mono text-[0.76em] transition',
        active ? tone.active : tone.idle,
        className
      )}
    >
      <span className="mr-px opacity-50" aria-hidden="true">
        ⟦
      </span>
      {children}
      <span className="ml-px opacity-50" aria-hidden="true">
        ⟧
      </span>
    </button>
  );
}
