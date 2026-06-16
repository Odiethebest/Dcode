import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import App from '@/App';

function renderApp() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('App shell', () => {
  it('renders both nav links', () => {
    renderApp();
    expect(screen.getByText('Index')).toBeInTheDocument();
    expect(screen.getByText('Query')).toBeInTheDocument();
    expect(screen.getByText('Compare')).toBeInTheDocument();
  });

  it('lands on the Index page by default', () => {
    renderApp();
    expect(screen.getByText(/Index a repository/i)).toBeInTheDocument();
  });
});
