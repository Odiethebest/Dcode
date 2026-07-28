import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { RepoSwitcher } from '@/components/workbench/RepoSwitcher';

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
