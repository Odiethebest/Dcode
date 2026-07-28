import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import MethodologyPage from '@/pages/MethodologyPage';

function renderMethodology() {
  return render(
    <MemoryRouter>
      <MethodologyPage />
    </MemoryRouter>
  );
}

describe('MethodologyPage', () => {
  it('reports the honest H1 verdict from the snapshot', () => {
    renderMethodology();
    expect(screen.getByText(/currently unsupported/i)).toBeInTheDocument();
    // B4's recorded groundedness (0.984375 -> 0.984), not an invented 1.00.
    expect(screen.getByText('0.984')).toBeInTheDocument();
  });

  it('routes the demo CTA into the workbench', () => {
    renderMethodology();
    expect(screen.getByRole('link', { name: /Open the demo/i })).toHaveAttribute('href', '/workbench');
  });

  it('switches question transcripts by taxonomy', () => {
    renderMethodology();
    // L2 is the default level -> the basic-auth question is shown.
    expect(screen.getAllByText(/attach basic auth/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'L3' }));
    expect(screen.getAllByText(/end-to-end send flow/i).length).toBeGreaterThan(0);
  });
});
