import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import QueryPage from '@/pages/QueryPage';

vi.mock('@/api/client', () => ({
  streamQuery: vi.fn(),
}));

import { streamQuery } from '@/api/client';

describe('QueryPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem(
      'dcode.recent-repos',
      JSON.stringify([
        {
          repoId: 'repo-123',
          url: 'https://github.com/psf/requests.git',
          status: 'ready',
          savedAt: '2026-06-16T00:00:00.000Z',
        },
      ])
    );
    vi.mocked(streamQuery).mockReset();
  });

  it('renders streamed events, final answer, and citations', async () => {
    vi.mocked(streamQuery).mockImplementation(async (_body, onEvent) => {
      onEvent({ event: 'thought', data: { step: 1, content: 'route to definition lookup' } });
      onEvent({
        event: 'tool_call',
        data: { step: 1, tool: 'find_definition', args: { symbol: 'HTTPBasicAuth' } },
      });
      onEvent({
        event: 'citation',
        data: {
          symbol: 'src.requests.auth.HTTPBasicAuth',
          file_path: 'src/requests/auth.py',
          line: 85,
          verified: true,
        },
      });
      onEvent({
        event: 'final_answer',
        data: {
          answer: 'Definition matches:\n- `src.requests.auth.HTTPBasicAuth`',
          citations: [
            {
              symbol: 'src.requests.auth.HTTPBasicAuth',
              file_path: 'src/requests/auth.py',
              line: 85,
              verified: true,
            },
          ],
          groundedness: 1,
        },
      });
    });

    render(<QueryPage />);

    fireEvent.click(screen.getByRole('button', { name: /run query/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/Definition matches/i).length).toBeGreaterThan(0);
    });
    expect(screen.getByText(/route to definition lookup/i)).toBeInTheDocument();
    expect(screen.getByText(/find_definition/i)).toBeInTheDocument();
    expect(screen.getByText(/groundedness 1.00/i)).toBeInTheDocument();
    expect(screen.getAllByText(/verified/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/src\/requests\/auth\.py:85/i).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(streamQuery).toHaveBeenCalledWith(
        { repo_id: 'repo-123', query: 'Where is `HTTPBasicAuth` defined?' },
        expect.any(Function),
        expect.any(AbortSignal)
      );
    });
  });
});
