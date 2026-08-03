import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { getSession } from '@/api/client';

// The workbench sits behind a session check, so every render of it now waits
// on one request. Stubbed to the ungated answer — the gate's own behaviour is
// covered in RequireSession.test.tsx rather than incidentally here.
vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  getSession: vi.fn(),
}));

const mockedGetSession = vi.mocked(getSession);

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
  beforeEach(() => {
    mockedGetSession.mockResolvedValue({
      auth_required: false,
      authenticated: true,
      username: null,
    });
  });

  it('renders the marketing landing at /', () => {
    renderAppAt('/');
    expect(screen.getByText(/Understand any codebase/i)).toBeInTheDocument();
  });

  it('renders the workbench at /workbench', async () => {
    renderAppAt('/workbench');
    expect(await screen.findByText(/ask this codebase anything/i)).toBeInTheDocument();
  });

  it('renders the login page at /login', () => {
    renderAppAt('/login');
    expect(screen.getByRole('heading', { name: /sign in to the workbench/i })).toBeInTheDocument();
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
