import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';

import { getRepoStatus, submitRepo } from '@/api/client';
import type { RepoStatusResponse } from '@/api/types';
import type { PillStatus } from '@/components/ui';
import { cx } from '@/lib/cx';
import { loadRecentRepos, saveRecentRepo, type RecentRepoRecord } from '@/lib/recentRepos';
import { toKnownRepoStatus } from '@/lib/repoStatus';

const TERMINAL = new Set(['ready', 'failed']);

/** Collapse the 7 repo states onto the three StatusPill buckets. */
function bucketOf(status: string): PillStatus {
  const s = toKnownRepoStatus(status);
  if (s === 'ready') return 'ready';
  if (s === 'failed') return 'failed';
  return 'indexing';
}

/**
 * Human label for a repo's live status. The active repo is polled, so we show
 * the moving stage (cloning → parsing → embedding → graphing) rather than a
 * frozen coarse percentage — progress is set per-stage, so the bar sits still
 * for the whole (slow, real-model) embedding stage and reads as "stuck". The
 * stage name changing is the reassurance that it's working.
 */
export function repoStatusLabel(status: string): string {
  const s = toKnownRepoStatus(status);
  if (s === 'ready') return 'ready';
  if (s === 'failed') return 'failed';
  if (s === 'queued') return 'queued';
  return `indexing · ${s}`;
}

/** owner/repo from a git URL, for a compact switcher label. */
function repoSlug(url: string): string {
  const cleaned = url.replace(/\.git$/, '').replace(/\/+$/, '');
  const parts = cleaned.split('/').filter(Boolean);
  return parts.slice(-2).join('/') || url;
}

const dotColor: Record<PillStatus, string> = {
  ready: 'bg-good',
  indexing: 'bg-warn',
  failed: 'bg-bad',
};

export interface RepoSwitcherProps {
  activeRepoId: string | null;
  onSelect: (repoId: string) => void;
}

/**
 * Topbar repo switcher (replaces the Index page). Lists the localStorage
 * recents, polls the active repo's live status (GET /repos/{id}/status) so
 * `indexing…` progress shows in place, and indexes a new repo (POST /repos)
 * from the dropdown. Selecting a repo scopes the whole workbench to it.
 */
export function RepoSwitcher({ activeRepoId, onSelect }: RepoSwitcherProps) {
  const [open, setOpen] = useState(false);
  const [recents, setRecents] = useState<RecentRepoRecord[]>(() => loadRecentRepos());
  const [adding, setAdding] = useState(false);
  const [url, setUrl] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const submit = useMutation({
    mutationFn: submitRepo,
    onSuccess: (response, variables) => {
      setRecents(
        saveRecentRepo({
          repoId: response.repo_id,
          url: variables.url,
          status: response.status,
          savedAt: new Date().toISOString(),
        })
      );
      onSelect(response.repo_id);
      setAdding(false);
      setUrl('');
    },
  });

  const statusQuery = useQuery({
    queryKey: ['repo-status', activeRepoId],
    queryFn: () => getRepoStatus(activeRepoId as string),
    enabled: Boolean(activeRepoId),
    refetchInterval: (query) => {
      const data = query.state.data as RepoStatusResponse | undefined;
      return data && TERMINAL.has(data.status) ? false : 1500;
    },
  });
  const liveStatus = statusQuery.data;
  const liveRepoId = liveStatus?.repo_id;
  const liveRepoStatus = liveStatus?.status;
  const liveRepoUrl = liveStatus?.url;

  // Persist the active repo's live status back into the recents cache.
  //
  // Keyed on the primitive fields rather than the response object: polling hands
  // back a new object every 1.5s, so depending on it rewrote localStorage on
  // every tick of an index that can run for minutes. Reads from storage rather
  // than from `recents` so the write stays out of a state updater (StrictMode
  // double-invokes those) and doesn't need `recents` in the dependency list.
  useEffect(() => {
    if (!liveRepoId || !liveRepoStatus) return;
    const existing = loadRecentRepos().find((item) => item.repoId === liveRepoId);
    if (existing?.status === liveRepoStatus) return;
    setRecents(
      saveRecentRepo({
        repoId: liveRepoId,
        // Prefer the URL the user actually typed over the server's normalised one.
        url: existing?.url ?? liveRepoUrl ?? '',
        status: liveRepoStatus,
        savedAt: existing?.savedAt ?? new Date().toISOString(),
      })
    );
  }, [liveRepoId, liveRepoStatus, liveRepoUrl]);

  const activeRepo = useMemo(
    () => recents.find((item) => item.repoId === activeRepoId) ?? null,
    [recents, activeRepoId]
  );
  const activeBucket = liveStatus
    ? bucketOf(liveStatus.status)
    : activeRepo
      ? bucketOf(activeRepo.status)
      : null;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2.5 rounded-[10px] border border-line-2 bg-surface px-3 py-[7px] transition hover:border-brand hover:bg-brand-wash"
      >
        <span
          className={cx('h-[7px] w-[7px] flex-none rounded-full', activeBucket ? dotColor[activeBucket] : 'bg-ink-3')}
          aria-hidden="true"
        />
        <span className="max-w-[180px] truncate font-mono text-[13px] font-medium text-ink">
          {activeRepo ? repoSlug(activeRepo.url) : 'select a repo'}
        </span>
        {activeBucket === 'indexing' && liveStatus && (
          <span className="flex-none font-mono text-[11px] text-warn">· {liveStatus.status}</span>
        )}
        <svg
          width="13"
          height="13"
          viewBox="0 0 14 14"
          fill="none"
          className={cx('flex-none text-ink-3 transition-transform', open && 'rotate-180')}
          aria-hidden="true"
        >
          <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 top-[calc(100%+8px)] z-40 min-w-[300px] rounded-xl border border-line bg-surface p-1.5 shadow-[0_24px_48px_-22px_rgba(27,24,38,0.4)]">
          <div className="px-3 pb-1.5 pt-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">
            Indexed repositories
          </div>

          {recents.length === 0 ? (
            <p className="px-3 py-3 text-sm text-ink-3">None yet — index one below.</p>
          ) : (
            recents.map((repo) => {
              const isActive = repo.repoId === activeRepoId;
              const bucket = bucketOf(isActive && liveStatus ? liveStatus.status : repo.status);
              const progress =
                isActive && liveStatus && bucket === 'indexing' ? liveStatus.progress : null;
              // The live (active) repo shows its moving stage; others show the
              // coarse bucket from their last-known stored status.
              const meta = isActive && liveStatus ? repoStatusLabel(liveStatus.status) : bucket;
              return (
                <button
                  key={repo.repoId}
                  type="button"
                  onClick={() => {
                    onSelect(repo.repoId);
                    setOpen(false);
                  }}
                  className={cx(
                    'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition hover:bg-sunk',
                    isActive && 'bg-brand-wash'
                  )}
                >
                  <span className={cx('h-[7px] w-[7px] flex-none rounded-full', dotColor[bucket])} aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-[13px] text-ink">{repoSlug(repo.url)}</span>
                    <span className="mt-0.5 block text-[11px] text-ink-3">{meta}</span>
                  </span>
                  {progress != null && (
                    <span className="h-1 w-11 flex-none overflow-hidden rounded-full bg-sunk" aria-hidden="true">
                      <span className="block h-full bg-warn" style={{ width: `${progress}%` }} />
                    </span>
                  )}
                </button>
              );
            })
          )}

          {adding ? (
            <form
              className="border-t border-line p-2"
              onSubmit={(event) => {
                event.preventDefault();
                const trimmed = url.trim();
                if (trimmed) submit.mutate({ url: trimmed });
              }}
            >
              <input
                autoFocus
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://github.com/owner/repo.git"
                className="w-full rounded-md border border-line-2 bg-paper px-2.5 py-2 font-mono text-[12px] text-ink outline-none transition focus:border-brand"
              />
              <div className="mt-2 flex gap-2">
                <button
                  type="submit"
                  disabled={submit.isPending}
                  className="flex-1 rounded-md bg-brand px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submit.isPending ? 'Submitting…' : 'Index'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAdding(false);
                    setUrl('');
                  }}
                  className="rounded-md border border-line-2 px-3 py-1.5 text-sm text-ink-2 transition hover:bg-sunk"
                >
                  Cancel
                </button>
              </div>
              {submit.isError && (
                <p className="mt-2 text-[12px] text-bad">Couldn’t queue that repo — check the URL.</p>
              )}
            </form>
          ) : (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="mt-1 flex w-full items-center gap-2 rounded-b-lg border-t border-line px-3 py-2.5 text-left text-[13px] font-semibold text-brand transition hover:bg-brand-wash"
            >
              + Index a new repository
            </button>
          )}
        </div>
      )}
    </div>
  );
}
