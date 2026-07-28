import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import LandingPage from '@/pages/LandingPage';

// Reduced motion so the proof card jumps straight to its verified end state
// (no timers left pending) and Reveal shows its content immediately.
function mockReducedMotion() {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('prefers-reduced-motion'),
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  );
}

describe('LandingPage', () => {
  beforeEach(() => mockReducedMotion());
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('leads with the hero promise', () => {
    renderLanding();
    expect(screen.getByRole('heading', { name: /Understand any codebase/i })).toBeInTheDocument();
  });

  it('routes every "Open the demo" CTA into the workbench', () => {
    renderLanding();
    const ctas = screen.getAllByRole('link', { name: /Open the demo/i });
    expect(ctas.length).toBeGreaterThan(0);
    for (const cta of ctas) {
      expect(cta).toHaveAttribute('href', '/workbench');
    }
  });

  it('settles the proof card to verified under reduced motion', () => {
    renderLanding();
    expect(screen.getAllByText(/^verified$/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/verifying/i)).not.toBeInTheDocument();
  });
});
