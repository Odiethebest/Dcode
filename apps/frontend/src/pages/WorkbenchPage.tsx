import { useState } from 'react';

import { HistoryRail } from '@/components/workbench/HistoryRail';
import { InspectorPane } from '@/components/workbench/InspectorPane';
import { ThreadPane } from '@/components/workbench/ThreadPane';
import { Topbar } from '@/components/workbench/Topbar';
import { cx } from '@/lib/cx';
import { loadRecentRepos } from '@/lib/recentRepos';

/**
 * The single continuous exploration workbench (replaces the Index/Query/Compare
 * tab IA). Three panes — history rail · thread · inspector — that collapse into
 * drawers on narrow viewports. Slice 1: static shell + responsive behavior; the
 * repo switcher, SSE thread, and inspector are wired in later slices.
 */
export default function WorkbenchPage() {
  const [showRail, setShowRail] = useState(false);
  const [showCode, setShowCode] = useState(false);
  // Active repo scopes the whole workbench (thread + inspector). Default to the
  // most recent so the workbench opens on something rather than empty.
  const [activeRepoId, setActiveRepoId] = useState<string | null>(
    () => loadRecentRepos()[0]?.repoId ?? null
  );
  const closeDrawers = () => {
    setShowRail(false);
    setShowCode(false);
  };

  return (
    <div className="flex h-[100dvh] flex-col bg-paper text-ink">
      <Topbar
        activeRepoId={activeRepoId}
        onSelectRepo={setActiveRepoId}
        onToggleRail={() => setShowRail(true)}
        onToggleCode={() => setShowCode(true)}
      />

      <div className="grid min-h-0 flex-1 grid-cols-[262px_1fr_384px] max-[1180px]:grid-cols-[240px_1fr] max-[760px]:grid-cols-[1fr]">
        <HistoryRail open={showRail} />
        <ThreadPane />
        <InspectorPane open={showCode} onClose={() => setShowCode(false)} />
      </div>

      {/* Scrim for the mobile drawers. */}
      <button
        type="button"
        aria-label="Close menu"
        tabIndex={showRail || showCode ? 0 : -1}
        onClick={closeDrawers}
        className={cx(
          'fixed inset-0 z-[45] bg-[rgba(20,17,30,0.4)] transition-opacity duration-200',
          showRail || showCode ? 'opacity-100' : 'pointer-events-none invisible opacity-0'
        )}
      />
    </div>
  );
}
