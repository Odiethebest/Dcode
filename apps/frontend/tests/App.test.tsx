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
  it('renders the marketing landing at /', () => {
    renderAppAt('/');
    expect(screen.getByText(/Understand any codebase/i)).toBeInTheDocument();
  });

  it('renders the workbench at /workbench', () => {
    renderAppAt('/workbench');
    expect(screen.getByText(/ask this codebase anything/i)).toBeInTheDocument();
  });

  it('renders the methodology page at /methodology', () => {
    renderAppAt('/methodology');
    expect(screen.getByText(/currently unsupported/i)).toBeInTheDocument();
  });

  it('renders the primitives gallery at /preview', () => {
    renderAppAt('/preview');
    expect(screen.getByText(/check the identity/i)).toBeInTheDocument();
  });

  it('no longer serves the retired legacy IA', () => {
    // Phase 4 deleted the Index/Query/Compare pages outright. Nothing linked to
    // them and they were still on the pre-token palette, so a redirect would
    // have served no one.
    for (const path of ['/legacy/index', '/legacy/query', '/legacy/compare']) {
      const { unmount } = renderAppAt(path);
      expect(document.body.textContent?.trim()).toBe('');
      unmount();
    }
  });
});
