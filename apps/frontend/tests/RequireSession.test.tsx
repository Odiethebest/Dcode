import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getSession } from '@/api/client';
import { RequireSession } from '@/components/RequireSession';

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  getSession: vi.fn(),
}));

const mockedGetSession = vi.mocked(getSession);

function renderGuard() {
  return render(
    <MemoryRouter initialEntries={['/workbench']}>
      <Routes>
        <Route
          path="/workbench"
          element={
            <RequireSession>
              <p>workbench body</p>
            </RequireSession>
          }
        />
        <Route path="/login" element={<p>login page</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RequireSession', () => {
  beforeEach(() => {
    mockedGetSession.mockReset();
  });

  it('shows neither the workbench nor a redirect while the answer is unknown', () => {
    // Three states, not two. Rendering either outcome during the check would
    // assert something that has not arrived yet — the same rule the thread
    // follows for turn state (Honesty_Constraints §1).
    mockedGetSession.mockReturnValue(new Promise(() => {}));
    renderGuard();

    expect(screen.getByRole('status')).toHaveTextContent(/checking session/i);
    expect(screen.queryByText('workbench body')).not.toBeInTheDocument();
    expect(screen.queryByText('login page')).not.toBeInTheDocument();
  });

  it('redirects to the login page when a gate exists and there is no session', async () => {
    mockedGetSession.mockResolvedValue({
      auth_required: true,
      authenticated: false,
      username: null,
    });
    renderGuard();

    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(screen.queryByText('workbench body')).not.toBeInTheDocument();
  });

  it('renders the workbench once a session is present', async () => {
    mockedGetSession.mockResolvedValue({
      auth_required: true,
      authenticated: true,
      username: 'reviewer',
    });
    renderGuard();

    expect(await screen.findByText('workbench body')).toBeInTheDocument();
  });

  it('does not gate a deployment that has no gate', async () => {
    // With AUTH_ENABLED off the API reports auth_required: false. Redirecting
    // to a login page that would accept anything is worse than not gating.
    mockedGetSession.mockResolvedValue({
      auth_required: false,
      authenticated: true,
      username: null,
    });
    renderGuard();

    expect(await screen.findByText('workbench body')).toBeInTheDocument();
  });

  it('fails open when the session check itself fails', async () => {
    // Deliberate: this guard is a redirect, not the security boundary. The
    // gateway answers 401 on every protected route no matter what the SPA
    // renders, so locking the UI out on a blip would break the product
    // without protecting anything.
    mockedGetSession.mockRejectedValue(new Error('network down'));
    renderGuard();

    expect(await screen.findByText('workbench body')).toBeInTheDocument();
  });
});
