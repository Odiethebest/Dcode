import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Turn } from '@/hooks/useThread';
import WorkbenchPage from '@/pages/WorkbenchPage';

// A completed turn whose answer carries an inline (clickable) citation chip.
const citationTurn: Turn = {
  id: 'turn-1',
  question: 'where is HTTPBasicAuth?',
  closed: true,
  events: [
    {
      event: 'citation',
      data: { symbol: 'HTTPBasicAuth', file_path: 'src/requests/auth.py', line: 85, verified: true },
    },
    {
      event: 'final_answer',
      data: {
        answer: 'It is in `src/requests/auth.py:85`.',
        citations: [{ symbol: 'HTTPBasicAuth', file_path: 'src/requests/auth.py', line: 85, verified: true }],
        groundedness: 1,
      },
    },
  ],
};

vi.mock('@/hooks/useThread', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/useThread')>();
  return { ...actual, useThread: () => ({ turns: [citationTurn], isStreaming: false, submit: vi.fn() }) };
});

function mockViewport(belowDrawerBreakpoint: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: belowDrawerBreakpoint,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function renderWorkbench() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkbenchPage />
    </QueryClientProvider>
  );
}

describe('workbench drawer scrim', () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('desktop: repeated citation clicks never open the scrim or add a second node', () => {
    mockViewport(false); // > 1180px
    renderWorkbench();

    const chip = screen.getByRole('button', { name: /auth\.py:85/ });
    for (let i = 0; i < 5; i += 1) fireEvent.click(chip);

    const scrims = screen.getAllByTestId('drawer-scrim');
    expect(scrims).toHaveLength(1); // single element — never accumulates
    expect(scrims[0].dataset.open).toBe('false'); // stays closed on desktop → no overlay
  });

  it('mobile: a citation click opens the single scrim', () => {
    mockViewport(true); // <= 1180px
    renderWorkbench();

    fireEvent.click(screen.getByRole('button', { name: /auth\.py:85/ }));

    const scrims = screen.getAllByTestId('drawer-scrim');
    expect(scrims).toHaveLength(1);
    expect(scrims[0].dataset.open).toBe('true');
  });
});
