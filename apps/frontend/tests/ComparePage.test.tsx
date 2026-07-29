import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { demoCases } from '@/demo/evalSnapshot';
import ComparePage from '@/pages/ComparePage';

// Legacy page, retired in Phase 4. Kept passing (and question-agnostic) only so
// the suite stays green until it is deleted.
describe('ComparePage', () => {
  it('shows H1 summary and lets the user switch demo cases', async () => {
    render(<ComparePage />);

    expect(screen.getByText(/B4 beats both B2 and B3/i)).toBeInTheDocument();
    expect(screen.getByText('unsupported')).toBeInTheDocument();

    const firstL2 = demoCases.find((c) => c.taxonomy === 'L2');
    const firstL3 = demoCases.find((c) => c.taxonomy === 'L3');
    expect(firstL2 && firstL3).toBeTruthy();
    expect(screen.getAllByText(firstL2!.question).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: 'L3' }));
    fireEvent.click(screen.getByRole('button', { name: new RegExp(firstL3!.questionId, 'i') }));

    expect((await screen.findAllByText(firstL3!.question)).length).toBeGreaterThan(0);
    expect(screen.getAllByText('grounded').length).toBeGreaterThan(0);
  });
});
