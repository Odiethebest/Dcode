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

/**
 * Aborted mid-stream: the citations already flushed (they arrive just before
 * `final_answer`), but `final_answer` never did — so groundedness never got to
 * redact the draft.
 */
function interruptedTurn(stopped: boolean): TurnData {
  return {
    id: 't3',
    question: 'How is auth wired?',
    closed: true,
    stopped,
    events: [
      ...baseEvents,
      {
        event: 'citation',
        data: { symbol: 'HTTPBasicAuth.__call__', file_path: 'src/requests/auth.py', line: 85, verified: true },
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

describe('Turn interrupted honesty', () => {
  it('never renders an aborted turn as done: no chips, no Sources, no groundedness', () => {
    const { container } = render(
      <Turn turn={interruptedTurn(true)} activeCitationKey={null} onOpenCitation={() => {}} />
    );

    // The pill reports interruption, never a grounded score.
    expect(screen.getByRole('button', { name: /interrupted/i })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain('grounded');

    // A citation event DID arrive before the abort — it still must not bind. The
    // ref stays an inert CodeChip, and nothing lands in a Sources footer.
    expect(screen.queryByRole('button', { name: /auth\.py:85/ })).toBeNull();
    expect(screen.getByText(/auth\.py:85/).tagName).toBe('CODE');
    expect(screen.queryByText('Sources')).toBeNull();

    // The draft is kept but labelled in plain prose, not a subtle badge.
    expect(screen.getByText(/Draft · never verified/i)).toBeInTheDocument();
    expect(screen.getByText(/never checked against the index/i)).toBeInTheDocument();

    // Static pill — a pulse on a stopped stream would imply work still running.
    expect(container.querySelector('.animate-pulse')).toBeNull();
  });

  it('distinguishes a deliberate stop from a dropped stream', () => {
    const { unmount } = render(
      <Turn turn={interruptedTurn(true)} activeCitationKey={null} onOpenCitation={() => {}} />
    );
    expect(screen.getByText(/You stopped this answer/i)).toBeInTheDocument();
    unmount();

    render(<Turn turn={interruptedTurn(false)} activeCitationKey={null} onOpenCitation={() => {}} />);
    expect(screen.getByText(/The stream ended before verification/i)).toBeInTheDocument();
  });
});
