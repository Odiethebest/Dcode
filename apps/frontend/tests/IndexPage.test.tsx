import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import IndexPage from '@/pages/IndexPage';

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <IndexPage />
    </QueryClientProvider>
  );
}

describe('IndexPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('submits a repo and renders live status details', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ repo_id: 'repo-123', status: 'queued' }), {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            repo_id: 'repo-123',
            status: 'parsing',
            progress: 55,
            error: null,
            stages: {
              cloning: 'done',
              parsing: 'in_progress',
              embedding: 'pending',
              graphing: 'pending',
            },
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        )
      );

    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    fireEvent.change(screen.getByLabelText(/repository url/i), {
      target: { value: 'https://github.com/psf/requests.git' },
    });
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/v1\/repos$/),
        expect.objectContaining({ method: 'POST' })
      );
    });

    await waitFor(() => {
      expect(screen.getAllByText('repo-123')).toHaveLength(2);
    });
    await screen.findByText('55%');
    expect(screen.getAllByText('parsing').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('done')).toBeInTheDocument();
    expect(screen.getByText('in progress')).toBeInTheDocument();
    expect(screen.getByText('https://github.com/psf/requests.git')).toBeInTheDocument();
  });

  it('shows backend errors from submission failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(
        new Response('bad request', {
          status: 400,
        })
      )
    );

    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    await screen.findByText(/POST \/api\/v1\/repos failed: 400/i);
  });
});
