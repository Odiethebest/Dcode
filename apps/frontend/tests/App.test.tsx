import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import App from '@/App';

function renderAppAt(path: string) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('App IA', () => {
  it('renders the workbench at /', () => {
    renderAppAt('/');
    expect(screen.getByText('Dcode')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument();
  });

  it('keeps the legacy Index page reachable off-nav until Phase 4', () => {
    renderAppAt('/legacy/index');
    expect(screen.getByText(/Index a repository/i)).toBeInTheDocument();
  });
});
