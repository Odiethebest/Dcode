import { useEffect, useState } from 'react';

import type { CitationPayload } from '@/api/types';
import { HistoryRail } from '@/components/workbench/HistoryRail';
import { InspectorPane } from '@/components/workbench/InspectorPane';
import { ThreadPane } from '@/components/workbench/ThreadPane';
import { Topbar } from '@/components/workbench/Topbar';
import { useThread } from '@/hooks/useThread';
import { citationKey } from '@/lib/citations';
import { cx } from '@/lib/cx';
import { loadRecentRepos } from '@/lib/recentRepos';

/**
 * The single continuous exploration workbench (replaces the Index/Query/Compare
 * tab IA). Owns the active repo + the SSE thread; three panes collapse into
 * drawers on narrow viewports.
 */
export default function WorkbenchPage() {
  const [showRail, setShowRail] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [activeRepoId, setActiveRepoId] = useState<string | null>(
    () => loadRecentRepos()[0]?.repoId ?? null
  );
  const [activeCitation, setActiveCitation] = useState<CitationPayload | null>(null);

  const { turns, submit } = useThread(activeRepoId);

  // A new repo means a new thread + no selected source.
  useEffect(() => setActiveCitation(null), [activeRepoId]);

  const closeDrawers = () => {
    setShowRail(false);
    setShowCode(false);
  };

  const openCitation = (citation: CitationPayload) => {
    setActiveCitation(citation);
    setShowCode(true); // reveal the inspector drawer on narrow viewports
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
        <HistoryRail open={showRail} turns={turns} onNavigate={() => setShowRail(false)} />
        <ThreadPane
          turns={turns}
          canSubmit={Boolean(activeRepoId)}
          onSubmit={submit}
          activeCitationKey={activeCitation ? citationKey(activeCitation) : null}
          onOpenCitation={openCitation}
        />
        <InspectorPane open={showCode} onClose={() => setShowCode(false)} citation={activeCitation} />
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
