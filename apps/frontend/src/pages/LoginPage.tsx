import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { UnauthenticatedError, login } from '@/api/client';
import { Button } from '@/components/ui';

/**
 * The gate between the landing page and the workbench (Deploy.md D-2).
 *
 * One shared account, so there is no "sign up", no "forgot password" and no
 * account menu — offering any of them would imply an identity system that does
 * not exist (D-6).
 */
export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login({ username, password });
      navigate('/workbench', { replace: true });
    } catch (caught) {
      // A wrong password and an unreachable gateway are different problems and
      // are worth different sentences: one is the reader's to fix.
      setError(
        caught instanceof UnauthenticatedError
          ? 'Incorrect username or password.'
          : 'Could not reach the server. Check that the backend is running.'
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center bg-paper px-6 text-ink">
      <div className="w-full max-w-[380px]">
        <Link
          to="/"
          className="font-mono text-[12.5px] tracking-wide text-ink-3 transition hover:text-ink-2"
        >
          ← Dcode
        </Link>

        <h1 className="mt-6 font-display text-[30px] leading-tight tracking-[-0.01em]">
          Sign in to the workbench
        </h1>
        <p className="mt-2 font-sans text-[14.5px] leading-relaxed text-ink-2">
          The evaluation write-up is{' '}
          <Link to="/methodology" className="text-brand underline underline-offset-2">
            open to everyone
          </Link>
          . The workbench indexes repositories and calls metered models, so it is not.
        </p>

        <form onSubmit={onSubmit} className="mt-7 flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-[12.5px] font-semibold text-ink-2">Username</span>
            <input
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              className="rounded-[10px] border border-line-2 bg-surface px-3.5 py-2.5 font-sans text-[14.5px] text-ink outline-none transition focus:border-brand"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-[12.5px] font-semibold text-ink-2">Password</span>
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              className="rounded-[10px] border border-line-2 bg-surface px-3.5 py-2.5 font-sans text-[14.5px] text-ink outline-none transition focus:border-brand"
            />
          </label>

          {/* Announced, because a failed sign-in with no visible cause is the
              point at which a screen-reader user is stuck with no recourse. */}
          <p role="alert" aria-live="polite" className="min-h-[18px] font-sans text-[13px] text-bad">
            {error}
          </p>

          <Button type="submit" size="lg" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </main>
  );
}
