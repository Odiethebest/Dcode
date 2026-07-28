import type { ReactNode } from 'react';

import { cx } from '@/lib/cx';

const tones = {
  verified: {
    idle: 'border-transparent bg-brand-wash text-brand hover:border-brand',
    active: 'border-transparent bg-brand text-white',
  },
  unverified: {
    // Never solid. Amber outline + pale-amber fill — the same honest language as
    // VerifiedMark's hollow amber mark. Active adds a soft ring, not a fill, so an
    // unverified citation never reads as more emphasized (more trustworthy) than
    // a verified one. Solid emphasis is reserved for verified/active.
    idle: 'border-warn bg-warn-wash text-warn',
    active: 'border-warn bg-warn-wash text-warn ring-2 ring-[color-mix(in_srgb,var(--warn)_30%,transparent)]',
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
        'inline-flex items-center whitespace-nowrap rounded-md border px-[7px] py-0.5 align-[1px] font-mono text-[0.76em] transition',
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
