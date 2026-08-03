import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { UnauthenticatedError, login } from '@/api/client';
import LoginPage from '@/pages/LoginPage';

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  login: vi.fn(),
}));

const mockedLogin = vi.mocked(login);

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/workbench" element={<p>workbench body</p>} />
      </Routes>
    </MemoryRouter>
  );
}

// fireEvent rather than user-event: the latter is not a dependency of this
// workspace, and adding one for a single file is the larger change.
function submit(username = 'reviewer', password = 'pw') {
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: username } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
}

describe('LoginPage', () => {
  beforeEach(() => {
    mockedLogin.mockReset();
  });

  it('sends the reader to the workbench on success', async () => {
    mockedLogin.mockResolvedValue({
      auth_required: true,
      authenticated: true,
      username: 'reviewer',
    });
    renderLogin();
    submit();

    expect(await screen.findByText('workbench body')).toBeInTheDocument();
  });

  it('says the credentials are wrong when they are', async () => {
    mockedLogin.mockRejectedValue(new UnauthenticatedError());
    renderLogin();
    submit();

    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect username or password/i);
    expect(screen.queryByText('workbench body')).not.toBeInTheDocument();
  });

  it('distinguishes an unreachable server from a wrong password', async () => {
    // These are different problems and only one of them is the reader's to
    // fix. Collapsing them into "sign-in failed" sends someone hunting for a
    // typo while the backend is down.
    mockedLogin.mockRejectedValue(new Error('Failed to fetch'));
    renderLogin();
    submit();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not reach the server/i);
  });

  it('keeps the public evaluation write-up linked from the gate', () => {
    renderLogin();
    expect(screen.getByRole('link', { name: /open to everyone/i })).toHaveAttribute(
      'href',
      '/methodology'
    );
  });
});
