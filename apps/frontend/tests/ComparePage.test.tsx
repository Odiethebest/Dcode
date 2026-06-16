import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ComparePage from '@/pages/ComparePage';

describe('ComparePage', () => {
  it('shows H1 summary and lets the user switch demo cases', async () => {
    render(<ComparePage />);

    expect(screen.getByText(/H1 requires B4 to beat both B2 and B3/i)).toBeInTheDocument();
    expect(screen.getByText('unsupported')).toBeInTheDocument();
    expect(
      screen.getAllByText(/How does requests attach basic auth to a prepared request/i).length
    ).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: 'L3' }));
    fireEvent.click(screen.getByRole('button', { name: /q-015/i }));

    expect(
      (await screen.findAllByText(
        /Explain the end-to-end send flow from `requests\.api\.request` to `Session\.send`/i
      )).length
    ).toBeGreaterThan(0);
    expect(screen.getAllByText('suspect').length).toBeGreaterThan(0);
    expect(screen.getByText(/grounded 0.60/i)).toBeInTheDocument();
  });
});
