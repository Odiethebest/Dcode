import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';

import { getSession } from '@/api/client';

type Gate = 'checking' | 'allowed' | 'denied';

/**
 * Route guard for the workbench.
 *
 * Three states, not two. While the session check is in flight the answer is
 * genuinely unknown, and rendering either the workbench or a redirect would be
 * asserting something not yet known — the same reasoning as
 * Honesty_Constraints §1, where a turn's state is derived from what has
 * arrived rather than from a guess.
 *
 * It fails **open** on a network error, which is deliberate and worth being
 * explicit about: this is a convenience redirect, not the security boundary.
 * The gateway refuses every protected route with 401 regardless of what the
 * SPA renders, so a guard that locked the UI out whenever `/auth/me` blipped
 * would only break the product without protecting anything.
 */
export function RequireSession({ children }: { children: React.ReactNode }) {
  const [gate, setGate] = useState<Gate>('checking');

  useEffect(() => {
    let active = true;
    getSession()
      .then((session) => {
        if (!active) return;
        setGate(session.auth_required && !session.authenticated ? 'denied' : 'allowed');
      })
      .catch(() => {
        if (active) setGate('allowed');
      });
    return () => {
      active = false;
    };
  }, []);

  if (gate === 'checking') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-[100dvh] items-center justify-center bg-paper font-mono text-[12.5px] text-ink-3"
      >
        checking session…
      </div>
    );
  }

  if (gate === 'denied') {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
