import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { RepoSwitcher, repoStatusLabel } from '@/components/workbench/RepoSwitcher';

function renderSwitcher() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <RepoSwitcher activeRepoId={null} onSelect={() => {}} />
    </QueryClientProvider>
  );
}

describe('RepoSwitcher', () => {
  beforeEach(() => window.localStorage.clear());

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
