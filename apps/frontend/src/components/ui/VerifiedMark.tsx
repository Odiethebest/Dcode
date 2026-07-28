import { cx } from '@/lib/cx';

const wrap =
  'inline-flex items-center gap-1.5 rounded-full px-2 py-[3px] font-mono text-[9.5px] font-medium uppercase tracking-[0.1em]';

export interface VerifiedMarkProps {
  verified?: boolean;
  className?: string;
}

/**
 * The signature verified stamp. `verified: false` is rendered honestly — amber,
 * a hollow (not-a-check) glyph, "unverified" — never a green check, since the
 * agent's groundedness check is trustworthy.
 */
export function VerifiedMark({ verified = true, className }: VerifiedMarkProps) {
  if (verified) {
    return (
      <span className={cx(wrap, 'bg-good-wash text-good', className)}>
        <svg viewBox="0 0 12 12" fill="none" className="h-2.5 w-2.5" aria-hidden="true">
          <path
            d="M2.5 6.2l2.2 2.3 4.8-5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        verified
      </span>
    );
  }
  return (
    <span className={cx(wrap, 'bg-warn-wash text-warn', className)}>
      <svg viewBox="0 0 12 12" fill="none" className="h-2.5 w-2.5" aria-hidden="true">
        <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.6" />
      </svg>
      unverified
    </span>
  );
}
