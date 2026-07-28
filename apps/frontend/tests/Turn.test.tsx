import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Turn } from '@/components/workbench/Turn';
import type { Turn as TurnData } from '@/hooks/useThread';

const baseEvents: TurnData['events'] = [
  { event: 'thought', data: { step: 1, content: 'Look at the auth path.' } },
  { event: 'tool_call', data: { step: 1, tool: 'search_code', args: { query: 'auth' } } },
  { event: 'partial_answer', data: { delta: 'Auth is set in `src/requests/auth.py:85`.' } },
];

function streamingTurn(): TurnData {
  return { id: 't1', question: 'How is auth wired?', closed: false, events: baseEvents };
}

function settledTurn(): TurnData {
  return {
    id: 't2',
    question: 'How is auth wired?',
    closed: true,
    events: [
      ...baseEvents,
      {
        event: 'citation',
        data: { symbol: 'HTTPBasicAuth.__call__', file_path: 'src/requests/auth.py', line: 85, verified: true },
      },
      {
        event: 'citation',
        data: { symbol: 'PreparedRequest.prepare_auth', file_path: 'src/requests/models.py', line: 471, verified: true },
      },
      {
        event: 'final_answer',
        data: { answer: 'Auth is set in `src/requests/auth.py:85`.', citations: [], groundedness: 1 },
      },
    ],
  };
}

describe('Turn two-phase honesty', () => {
  it('while streaming: neutral trace, no grounded score, refs are inert (no citation chip)', () => {
    render(<Turn turn={streamingTurn()} activeCitationKey={null} onOpenCitation={() => {}} />);

    expect(screen.getByRole('button', { name: /reasoning/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /auth\.py:85/ })).toBeNull(); // inert, not clickable
    expect(screen.queryByText('Sources')).toBeNull();
    expect(document.body.textContent).not.toContain('grounded');
  });

  it('at settle: grounded score, matched ref becomes a clickable chip, unmatched citation → Sources', () => {
    const onOpen = vi.fn();
    render(<Turn turn={settledTurn()} activeCitationKey={null} onOpenCitation={onOpen} />);

    expect(screen.getByRole('button', { name: /grounded 1\.00/ })).toBeInTheDocument();

    const chip = screen.getByRole('button', { name: /auth\.py:85/ });
    fireEvent.click(chip);
    expect(onOpen).toHaveBeenCalledWith(
      expect.objectContaining({ file_path: 'src/requests/auth.py', line: 85 })
    );

    // models.py:471 is never referenced in the prose → surfaced under Sources.
    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /models\.py:471/ })).toBeInTheDocument();
  });
});
