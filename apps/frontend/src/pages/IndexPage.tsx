import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { getRepoStatus, submitRepo } from '@/api/client';
import type { RepoStatusResponse, StagesStatus, UUID } from '@/api/types';
import { RepoStatusBadge } from '@/components/RepoStatusBadge';
import {
  loadRecentRepos,
  saveRecentRepo,
  type RecentRepoRecord,
} from '@/lib/recentRepos';

const DEFAULT_REPO_URL = 'https://github.com/psf/requests.git';
const TERMINAL_STATUSES = new Set(['ready', 'failed']);

const STAGE_ORDER: Array<keyof StagesStatus> = ['cloning', 'parsing', 'embedding', 'graphing'];

export default function IndexPage() {
  const navigate = useNavigate();
  const [repoUrl, setRepoUrl] = useState(DEFAULT_REPO_URL);
  const [currentRepoId, setCurrentRepoId] = useState<UUID | null>(null);
  const [recentRepos, setRecentRepos] = useState<RecentRepoRecord[]>(() => loadRecentRepos());

  const submitMutation = useMutation({
    mutationFn: submitRepo,
    onSuccess: (response) => {
      setCurrentRepoId(response.repo_id);
      setRecentRepos((current) =>
        upsertRecentRepo(
          current,
          saveRecentRepo({
            repoId: response.repo_id,
            url: repoUrl,
            status: response.status,
            savedAt: new Date().toISOString(),
          })
        )
      );
    },
  });

  const statusQuery = useQuery({
    queryKey: ['repo-status', currentRepoId],
    queryFn: () => getRepoStatus(currentRepoId as UUID),
    enabled: Boolean(currentRepoId),
    refetchInterval: (query) => {
      const data = query.state.data as RepoStatusResponse | undefined;
      if (!data || !TERMINAL_STATUSES.has(data.status)) {
        return 1500;
      }
      return false;
    },
  });

  const activeStatus = statusQuery.data;

  useEffect(() => {
    if (!activeStatus) {
      return;
    }

    setRecentRepos((current) => {
      const existing = current.find((item) => item.repoId === activeStatus.repo_id);
      return upsertRecentRepo(
        current,
        saveRecentRepo({
          repoId: activeStatus.repo_id,
          url: existing?.url ?? repoUrl,
          status: activeStatus.status,
          savedAt: existing?.savedAt ?? new Date().toISOString(),
        })
      );
    });
  }, [activeStatus, repoUrl]);

  const formError =
    (submitMutation.error instanceof Error && submitMutation.error.message) ||
    (statusQuery.error instanceof Error && statusQuery.error.message) ||
    activeStatus?.error ||
    null;

  return (
    <section className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[minmax(0,1.4fr)_20rem]">
      <div className="space-y-6">
        <header className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Index a repository</h1>
          <p className="max-w-3xl text-sm leading-6 text-stone-600">
            Submit a Git URL, track the worker state machine, and keep the resulting
            `repo_id` ready for the query flow.
          </p>
        </header>

        <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <form className="space-y-4" onSubmit={(event) => handleSubmit(event, repoUrl, submitMutation.mutate)}>
            <div className="space-y-2">
              <label htmlFor="repo-url" className="block text-sm font-medium text-stone-700">
                Repository URL
              </label>
              <input
                id="repo-url"
                name="repo-url"
                type="url"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                placeholder="https://github.com/owner/repo.git"
                required
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={submitMutation.isPending}
                className="inline-flex min-w-32 items-center justify-center rounded-md bg-stone-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-400"
              >
                {submitMutation.isPending ? 'Submitting…' : 'Submit'}
              </button>
              <button
                type="button"
                onClick={() => setRepoUrl(DEFAULT_REPO_URL)}
                className="inline-flex min-w-32 items-center justify-center rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-50"
              >
                Use requests
              </button>
            </div>
          </form>

          {formError ? (
            <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {formError}
            </p>
          ) : null}
        </section>

        <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-stone-900">Current job</h2>
              <p className="text-sm text-stone-600">
                Repo ID:{' '}
                <span className="font-mono text-stone-900">
                  {activeStatus?.repo_id ?? currentRepoId ?? 'Waiting for submission'}
                </span>
              </p>
            </div>
            <RepoStatusBadge value={activeStatus?.status ?? 'queued'} />
          </div>

          <div className="mt-5 space-y-3">
            <div>
              <div className="mb-2 flex items-center justify-between text-sm text-stone-600">
                <span>Progress</span>
                <span>{activeStatus?.progress ?? 0}%</span>
              </div>
              <div className="h-2 rounded-full bg-stone-200">
                <div
                  className="h-2 rounded-full bg-sky-600 transition-all"
                  style={{ width: `${activeStatus?.progress ?? 0}%` }}
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {STAGE_ORDER.map((stage) => (
                <div key={stage} className="rounded-md border border-stone-200 bg-stone-50 px-3 py-3">
                  <div className="mb-2 text-xs font-medium uppercase tracking-wide text-stone-500">
                    {stage}
                  </div>
                  <RepoStatusBadge value={activeStatus?.stages[stage] ?? 'pending'} />
                </div>
              ))}
            </div>

            {statusQuery.isFetching && currentRepoId ? (
              <p className="text-xs text-stone-500">Polling status…</p>
            ) : null}
            {activeStatus?.status === 'ready' && currentRepoId ? (
              <button
                type="button"
                onClick={() => navigate(`/query?repoId=${currentRepoId}`)}
                className="inline-flex items-center gap-2 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-500"
              >
                Query this repo →
              </button>
            ) : null}
            {activeStatus?.error ? (
              <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {activeStatus.error}
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <aside className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-stone-900">Recent repos</h2>
        <div className="mt-4 space-y-3">
          {recentRepos.length === 0 ? (
            <p className="text-sm text-stone-600">No submissions yet.</p>
          ) : (
            recentRepos.map((repo) => (
              <button
                key={repo.repoId}
                type="button"
                onClick={() => {
                  setRepoUrl(repo.url);
                  setCurrentRepoId(repo.repoId);
                }}
                className="block w-full rounded-md border border-stone-200 px-3 py-3 text-left transition hover:border-sky-300 hover:bg-sky-50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-stone-900">{repo.url}</p>
                    <p className="mt-1 truncate font-mono text-xs text-stone-500">{repo.repoId}</p>
                  </div>
                  <RepoStatusBadge value={toKnownRepoStatus(repo.status)} />
                </div>
              </button>
            ))
          )}
        </div>
      </aside>
    </section>
  );
}

function handleSubmit(
  event: FormEvent<HTMLFormElement>,
  repoUrl: string,
  submit: (variables: { url: string }) => void
) {
  event.preventDefault();
  submit({ url: repoUrl.trim() });
}

function upsertRecentRepo(
  current: RecentRepoRecord[],
  next: RecentRepoRecord[]
): RecentRepoRecord[] {
  if (next.length > 0) {
    return next;
  }
  return current;
}

function toKnownRepoStatus(status: string): 'queued' | 'cloning' | 'parsing' | 'embedding' | 'graphing' | 'ready' | 'failed' {
  switch (status) {
    case 'queued':
    case 'cloning':
    case 'parsing':
    case 'embedding':
    case 'graphing':
    case 'ready':
    case 'failed':
      return status;
    default:
      return 'queued';
  }
}
