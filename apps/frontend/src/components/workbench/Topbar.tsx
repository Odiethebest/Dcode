import type { ReactNode } from 'react';

import { cx } from '@/lib/cx';

function IconButton({
  label,
  onClick,
  className,
  children,
}: {
  label: string;
  onClick: () => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className={cx(
        'h-9 w-9 items-center justify-center rounded-[9px] text-ink-2 transition hover:bg-sunk',
        className
      )}
    >
      {children}
    </button>
  );
}

export interface TopbarProps {
  onToggleRail: () => void;
  onToggleCode: () => void;
}

/**
 * Workbench topbar. The repo switcher is a visual placeholder here — it's wired
 * to the real repo list + status in slice 2.
 */
export function Topbar({ onToggleRail, onToggleCode }: TopbarProps) {
  return (
    <header className="z-30 flex h-[58px] flex-none items-center gap-4 border-b border-line bg-[color-mix(in_srgb,var(--paper)_88%,transparent)] px-5 backdrop-blur-[8px]">
      <IconButton label="History" onClick={onToggleRail} className="hidden max-[760px]:flex">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M3 5h14M3 10h14M3 15h9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </IconButton>

      <div className="flex items-baseline gap-2 font-display text-[21px] font-semibold tracking-tight">
        Dcode
        <span className="h-1.5 w-1.5 -translate-y-0.5 rounded-full bg-brand" aria-hidden="true" />
      </div>

      <span className="h-[22px] w-px bg-line-2" aria-hidden="true" />

      {/* Repo switcher (placeholder — slice 2 wires the real list + status). */}
      <button
        type="button"
        className="flex items-center gap-2.5 rounded-[10px] border border-line-2 bg-surface px-3 py-[7px] transition hover:border-brand hover:bg-brand-wash"
      >
        <span className="h-[7px] w-[7px] rounded-full bg-ink-3" aria-hidden="true" />
        <span className="font-mono text-[13px] font-medium text-ink">select a repo</span>
        <svg width="13" height="13" viewBox="0 0 14 14" fill="none" className="text-ink-3" aria-hidden="true">
          <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <div className="flex-1" />

      <nav className="flex gap-1 max-[760px]:hidden">
        {['About', 'Methodology', 'GitHub'].map((label) => (
          <a
            key={label}
            href="#"
            className="rounded-lg px-2.5 py-[7px] text-[13.5px] text-ink-2 transition hover:bg-sunk hover:text-ink"
          >
            {label}
          </a>
        ))}
      </nav>

      <IconButton label="Code" onClick={onToggleCode} className="hidden max-[1180px]:flex">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M7 5l-4 5 4 5M13 5l4 5-4 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </IconButton>
    </header>
  );
}
