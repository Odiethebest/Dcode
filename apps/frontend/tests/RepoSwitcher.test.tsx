import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/api/client';
import type { RepoStatusResponse } from '@/api/types';
import { RepoSwitcher, repoStatusLabel } from '@/components/workbench/RepoSwitcher';
import { saveRecentRepo } from '@/lib/recentRepos';

vi.mock('@/api/client', () => ({ getRepoStatus: vi.fn(), submitRepo: vi.fn() }));

function renderSwitcher(activeRepoId: string | null = null, onSelect: (id: string) => void = () => {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RepoSwitcher activeRepoId={activeRepoId} onSelect={onSelect} />
    </QueryClientProvider>
  );
}

describe('RepoSwitcher', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('shows the empty active state and reveals the index-new-repo form', () => {
    renderSwitcher();
    expect(screen.getByText('select a repo')).toBeInTheDocument();

    fireEvent.click(screen.getByText('select a repo'));
    expect(screen.getByText('Indexed repositories')).toBeInTheDocument();
    expect(screen.getByText(/None yet/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('+ Index a new repository'));
    expect(screen.getByPlaceholderText(/github\.com/i)).toBeInTheDocument();
  });
});

describe('RepoSwitcher honesty when the gateway is unreachable', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('says the status is unavailable instead of replaying a cached ready', async () => {
    // The stored status is the last thing we saw, not a fact about now. Showing
    // a confident green "ready" for a repo we cannot reach claims something we
    // did not check — the same failure as the old stylised landing ladder.
    saveRecentRepo({
      repoId: 'repo-1',
      url: 'https://github.com/psf/requests.git',
      status: 'ready',
      savedAt: new Date().toISOString(),
    });
    vi.mocked(client.getRepoStatus).mockRejectedValue(new Error('Failed to fetch'));

    renderSwitcher('repo-1');

    expect(await screen.findByText(/status unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText('ready')).toBeNull();
  });

  it('labels non-polled repos as last-known rather than current', async () => {
    for (const repoId of ['repo-1', 'repo-2']) {
      saveRecentRepo({
        repoId,
        url: `https://github.com/psf/${repoId}.git`,
        status: 'ready',
        savedAt: new Date().toISOString(),
      });
    }
    vi.mocked(client.getRepoStatus).mockRejectedValue(new Error('Failed to fetch'));

    renderSwitcher('repo-1');
    fireEvent.click(screen.getByText('psf/repo-1'));

    // repo-2 is never polled, so its stored status is history, not a live claim.
    expect(await screen.findByText(/last known · ready/i)).toBeInTheDocument();
  });
});

describe('RepoSwitcher surfaces an incomplete or failed index', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    saveRecentRepo({
      repoId: 'repo-1',
      url: 'https://github.com/psf/requests.git',
      status: 'ready',
      savedAt: new Date().toISOString(),
    });
  });

  function status(overrides: Partial<RepoStatusResponse>): RepoStatusResponse {
    return {
      repo_id: 'repo-1',
      url: 'https://github.com/psf/requests.git',
      status: 'ready',
      progress: 100,
      stages: { cloning: 'done', parsing: 'done', embedding: 'done', graphing: 'done' },
      error: null,
      warnings: [],
      ...overrides,
    };
  }

  it('marks a repo whose index skipped files, without needing the dropdown open', async () => {
    // A partial index changes what any answer can possibly say. Hiding that
    // behind a click would let someone read a confidently incomplete answer.
    vi.mocked(client.getRepoStatus).mockResolvedValue(
      status({ warnings: ['src/huge.py: file too large', 'src/broken.py: parse error'] })
    );

    renderSwitcher('repo-1');

    expect(await screen.findByText('2 skipped')).toBeInTheDocument();
  });

  it('explains what a skipped file means and lists them on demand', async () => {
    vi.mocked(client.getRepoStatus).mockResolvedValue(
      status({ warnings: ['src/huge.py: file too large'] })
    );

    renderSwitcher('repo-1');
    fireEvent.click(await screen.findByText('psf/requests'));

    expect(await screen.findByText(/1 file skipped while indexing/i)).toBeInTheDocument();
    expect(screen.getByText(/no answer can cite them/i)).toBeInTheDocument();

    // The list itself is detail, so it starts collapsed.
    expect(screen.queryByText('src/huge.py: file too large')).toBeNull();
    fireEvent.click(screen.getByText(/1 file skipped while indexing/i));
    expect(screen.getByText('src/huge.py: file too large')).toBeInTheDocument();
  });

  it('shows why an index failed, not just that it did', async () => {
    vi.mocked(client.getRepoStatus).mockResolvedValue(
      status({ status: 'failed', progress: 0, error: 'Clone failed: repository not found' })
    );

    renderSwitcher('repo-1');
    fireEvent.click(await screen.findByText('psf/requests'));

    expect(await screen.findByText(/indexing failed/i)).toBeInTheDocument();
    expect(screen.getByText(/Clone failed: repository not found/i)).toBeInTheDocument();
  });

  it('stays quiet for a clean index', async () => {
    vi.mocked(client.getRepoStatus).mockResolvedValue(status({}));

    renderSwitcher('repo-1');
    fireEvent.click(await screen.findByText('psf/requests'));

    expect(screen.queryByText(/skipped/i)).toBeNull();
    expect(screen.queryByText(/indexing failed/i)).toBeNull();
  });
});

describe('RepoSwitcher idempotent submit', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('says "already indexed" when the gateway reused an existing repo', async () => {
    vi.mocked(client.getRepoStatus).mockResolvedValue({
      repo_id: 'repo-1',
      url: 'https://github.com/psf/requests.git',
      status: 'ready',
      progress: 100,
      stages: { cloning: 'done', parsing: 'done', embedding: 'done', graphing: 'done' },
      error: null,
      warnings: [],
    });
    vi.mocked(client.submitRepo).mockResolvedValue({
      repo_id: 'repo-1',
      status: 'ready',
      reused: true,
    });

    const onSelect = vi.fn();
    renderSwitcher(null, onSelect);

    fireEvent.click(screen.getByText('select a repo'));
    fireEvent.click(screen.getByText('+ Index a new repository'));
    fireEvent.change(screen.getByPlaceholderText(/github\.com/i), {
      target: { value: 'https://github.com/psf/requests.git' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Index' }));

    // Jumping straight to `ready` without a word would read as an implausibly
    // fast index rather than the no-op it is.
    expect(await screen.findByText(/already indexed — switched to it/i)).toBeInTheDocument();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('repo-1'));
  });

  it('stays quiet when a genuinely new repo was queued', async () => {
    vi.mocked(client.getRepoStatus).mockRejectedValue(new Error('not yet'));
    vi.mocked(client.submitRepo).mockResolvedValue({
      repo_id: 'repo-2',
      status: 'queued',
      reused: false,
    });

    renderSwitcher();
    fireEvent.click(screen.getByText('select a repo'));
    fireEvent.click(screen.getByText('+ Index a new repository'));
    fireEvent.change(screen.getByPlaceholderText(/github\.com/i), {
      target: { value: 'https://github.com/encode/httpx.git' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Index' }));

    await waitFor(() => expect(vi.mocked(client.submitRepo)).toHaveBeenCalled());
    expect(screen.queryByText(/already indexed/i)).toBeNull();
  });
});

describe('repoStatusLabel', () => {
  it('shows the moving stage while indexing, terminal labels otherwise', () => {
    // The whole point of the fix: the stage name changes even though the coarse
    // per-stage progress bar sits frozen (e.g. at 60% through embedding).
    expect(repoStatusLabel('cloning')).toBe('indexing · cloning');
    expect(repoStatusLabel('parsing')).toBe('indexing · parsing');
    expect(repoStatusLabel('embedding')).toBe('indexing · embedding');
    expect(repoStatusLabel('graphing')).toBe('indexing · graphing');
    expect(repoStatusLabel('queued')).toBe('queued');
    expect(repoStatusLabel('ready')).toBe('ready');
    expect(repoStatusLabel('failed')).toBe('failed');
  });
});
