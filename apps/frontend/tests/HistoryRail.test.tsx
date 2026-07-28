import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { HistoryRail } from '@/components/workbench/HistoryRail';
import type { Turn } from '@/hooks/useThread';

const doneTurn: Turn = {
  id: 'turn-1',
  question: 'How is auth wired?',
  closed: true,
  events: [
    {
      event: 'final_answer',
      data: {
        answer: 'x',
        citations: [{ symbol: 'A', file_path: 'a.py', line: 1, verified: true }],
        groundedness: 1,
      },
    },
  ],
};

describe('HistoryRail', () => {
  it('lists the thread turns and closes the drawer on tap', () => {
    const onNavigate = vi.fn();
    render(<HistoryRail open turns={[doneTurn]} onNavigate={onNavigate} />);

    expect(screen.getByText('How is auth wired?')).toBeInTheDocument();
    expect(screen.getByText(/grounded 1\.00/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('How is auth wired?'));
    expect(onNavigate).toHaveBeenCalled();
  });

  it('shows an empty state with no turns', () => {
    render(<HistoryRail open turns={[]} onNavigate={() => {}} />);
    expect(screen.getByText(/No questions yet/i)).toBeInTheDocument();
  });
});
