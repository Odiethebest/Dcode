import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as client from '@/api/client';
import type { CitationPayload, SourceResponse, SymbolNeighbors } from '@/api/types';
import { InspectorPane } from '@/components/workbench/InspectorPane';

// Keep Shiki/wasm out of jsdom — SourceView falls back to plain text.
vi.mock('@/lib/highlight', () => ({ highlightPython: async () => null }));
vi.mock('@/api/client', () => ({ getSource: vi.fn(), getNeighbors: vi.fn() }));

const prepareAuth: CitationPayload = {
  symbol: 'requests.models.PreparedRequest.prepare_auth',
  file_path: 'src/requests/models.py',
  line: 670,
  verified: true,
};

function sourceFor(symbol: string): SourceResponse {
  if (symbol.includes('HTTPBasicAuth')) {
    return {
      found: true,
      granularity: 'chunk',
      file_path: 'src/requests/auth.py',
      symbol_name: 'HTTPBasicAuth',
      chunk_type: 'class',
      start_line: 85,
      end_line: 90,
      cited_line: 85,
      content: 'class HTTPBasicAuth(AuthBase):\n    pass',
      outline: [],
      language: 'python',
    };
  }
  return {
    found: true,
    granularity: 'chunk',
    file_path: 'src/requests/models.py',
    symbol_name: 'PreparedRequest.prepare_auth',
    chunk_type: 'method',
    start_line: 668,
    end_line: 674,
    cited_line: 670,
    content: 'def prepare_auth(self, auth, url):\n    r = auth(self)',
    outline: [],
    language: 'python',
  };
}

function neighborsFor(symbol: string): SymbolNeighbors {
  return {
    found: true,
    symbol,
    file_path: 'src/requests/models.py',
    line: 670,
    called_by: [
      { symbol: 'requests.models.PreparedRequest.prepare', file_path: 'src/requests/models.py', line: 600, chunk_id: null },
    ],
    calls: [{ symbol: 'requests.auth.HTTPBasicAuth', file_path: 'src/requests/auth.py', line: 85, chunk_id: null }],
    references: [],
  };
}

function renderInspector() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <InspectorPane open onClose={() => {}} repoId="r1" citation={prepareAuth} />
    </QueryClientProvider>
  );
}

describe('InspectorPane', () => {
  beforeEach(() => {
    vi.mocked(client.getSource).mockImplementation(async (_repo, params) => sourceFor(params.symbol ?? ''));
    vi.mocked(client.getNeighbors).mockImplementation(async (_repo, symbol) => neighborsFor(symbol));
  });

  it('renders real source + call-graph for a citation and walks the graph on click', async () => {
    renderInspector();

    // Header + cited source for prepare_auth @ models.py:670.
    expect(await screen.findByText('src/requests/models.py')).toBeInTheDocument();
    expect(await screen.findByText(/line 670/)).toBeInTheDocument();
    expect(await screen.findByText(/r = auth\(self\)/)).toBeInTheDocument();

    // Call-graph groups + a clickable neighbor.
    expect(await screen.findByText('Called by')).toBeInTheDocument();
    expect(screen.getByText('Calls')).toBeInTheDocument();
    const neighbor = await screen.findByText('requests.auth.HTTPBasicAuth');

    // Walk to it -> source is refetched for the neighbor's location.
    fireEvent.click(neighbor);
    await waitFor(() =>
      expect(vi.mocked(client.getSource)).toHaveBeenCalledWith(
        'r1',
        expect.objectContaining({ symbol: 'requests.auth.HTTPBasicAuth', line: 85 })
      )
    );
  });

  it('stamps the cited node verified, but a walked node only indexed', async () => {
    renderInspector();

    // At the citation: it passed groundedness, so it earns the verified stamp.
    expect(await screen.findByText('verified')).toBeInTheDocument();
    expect(screen.queryByText('indexed')).toBeNull();

    // Walk one hop. Nothing about this node went through groundedness — it is in
    // the index, and that is the whole of what we may claim about it.
    fireEvent.click(await screen.findByText('requests.auth.HTTPBasicAuth'));

    expect(await screen.findByText('indexed')).toBeInTheDocument();
    expect(screen.queryByText('verified')).toBeNull();
    expect(screen.queryByText('unverified')).toBeNull();
  });
});
