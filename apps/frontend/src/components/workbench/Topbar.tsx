import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { RepoSwitcher } from '@/components/workbench/RepoSwitcher';
import { cx } from '@/lib/cx';
import { GITHUB_URL } from '@/lib/links';

const navLinkClass = 'rounded-lg px-2.5 py-[7px] text-[13.5px] text-ink-2 transition hover:bg-sunk hover:text-ink';

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
  activeRepoId: string | null;
  onSelectRepo: (repoId: string) => void;
  onToggleRail: () => void;
  onToggleCode: () => void;
}

export function Topbar({ activeRepoId, onSelectRepo, onToggleRail, onToggleCode }: TopbarProps) {
  return (
    <header className="z-30 flex h-[58px] flex-none items-center gap-4 border-b border-line bg-[color-mix(in_srgb,var(--paper)_88%,transparent)] px-5 backdrop-blur-[8px]">
      <IconButton label="History" onClick={onToggleRail} className="hidden max-[760px]:flex">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M3 5h14M3 10h14M3 15h9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </IconButton>

      <Link
        to="/"
        aria-label="Dcode home"
        className="flex items-baseline gap-2 font-display text-[21px] font-semibold tracking-tight"
      >
        Dcode
        <span className="h-1.5 w-1.5 -translate-y-0.5 rounded-full bg-brand" aria-hidden="true" />
      </Link>

      <span className="h-[22px] w-px bg-line-2" aria-hidden="true" />

      <RepoSwitcher activeRepoId={activeRepoId} onSelect={onSelectRepo} />

      <div className="flex-1" />

      <nav className="flex gap-1 max-[760px]:hidden">
        <Link to="/" className={navLinkClass}>
          Overview
        </Link>
        <Link to="/methodology" className={navLinkClass}>
          Methodology
        </Link>
        <a href={GITHUB_URL} target="_blank" rel="noreferrer" className={navLinkClass}>
          GitHub
        </a>
      </nav>

      <IconButton label="Code" onClick={onToggleCode} className="hidden max-[1180px]:flex">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M7 5l-4 5 4 5M13 5l4 5-4 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </IconButton>
    </header>
  );
}
