"""Single shared-account session auth for the gated deployment.

Deploy.md D-6 chose one shared account over per-reviewer accounts: no user
table, no migration, no account lifecycle. This module is what that decision
costs — roughly a hundred lines of stdlib and no new dependency. `passlib`,
`pyjwt` and `itsdangerous` are all absent from this workspace, and pulling one
in to authenticate a single demo account would be the larger change.

What it is not: an authorization model. There is one principal, a shared secret
cannot be revoked for one holder, and the daily query cap is therefore per
*session* rather than per person. Those limits are recorded in Deploy.md rather
than papered over here.

**Auth is off by default** (`AUTH_ENABLED=false`) so local development, the
existing test suite and every current compose invocation are unaffected
(Deploy.md §5.1). Production turns it on, and `docker-compose.prod.yml` hard-
codes it rather than defaulting it, so a deployment cannot forget. If it is on
and unconfigured the app refuses to start — an auth gate that fails open is
worse than none, because it looks like one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException, status

from dcode_api.settings import api_settings

SESSION_COOKIE_NAME = "dcode_session"

_HASH_SCHEME = "pbkdf2_sha256"
# Segments are joined with "." and NOT with passlib's conventional "$".
#
# Docker Compose interpolates `${VAR}` *and* bare `$VAR` inside env-file
# values. A `$`-separated hash therefore arrives at the container mangled:
# `pbkdf2_sha256$600000$salt$hash` lost three of its four segments in testing
# and shrank to 22 characters. Nothing errors — the value is still non-empty,
# the app still boots, and every login just fails forever. Escaping as `$$` in
# the env file would work and would be remembered by nobody, so the format
# avoids the character instead. The base64url alphabet has no ".", so this is
# unambiguous.
_HASH_SEPARATOR = "."
# OWASP's 2023 floor for PBKDF2-HMAC-SHA256. Encoded into the hash string, so
# raising it later does not invalidate credentials already issued.
_DEFAULT_ITERATIONS = 600_000
_SALT_BYTES = 16


# --- password hashing ----------------------------------------------------


def _parse_hash(encoded: str) -> tuple[int, bytes, bytes] | None:
    """Split an encoded hash, or None if it is not one."""
    try:
        scheme, raw_iterations, salt_b64, expected_b64 = encoded.split(_HASH_SEPARATOR)
        if scheme != _HASH_SCHEME:
            return None
        return int(raw_iterations), _b64decode(salt_b64), _b64decode(expected_b64)
    except (ValueError, TypeError):
        return None


def hash_password(password: str, *, iterations: int = _DEFAULT_ITERATIONS) -> str:
    """Encode a password as ``pbkdf2_sha256$iterations$salt$hash``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return _HASH_SEPARATOR.join(
        [_HASH_SCHEME, str(iterations), _b64encode(salt), _b64encode(derived)]
    )


def verify_password(password: str, encoded: str) -> bool:
    """Check a password against an encoded hash, in constant time.

    Returns False rather than raising on a malformed hash: a misconfigured
    `AUTH_PASSWORD_HASH` must deny access, not crash the request handler into
    a 500 that a caller could tell apart from a wrong password.
    """
    parsed = _parse_hash(encoded)
    if parsed is None:
        return False
    iterations, salt, expected = parsed

    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


# --- session tokens ------------------------------------------------------


@dataclass(frozen=True)
class SessionClaims:
    """A validated session. `jti` scopes the per-session daily query budget."""

    sub: str
    jti: str
    issued_at: int
    expires_at: int


def issue_session(username: str, *, ttl_seconds: int, secret: str) -> str:
    """Mint a signed ``payload.signature`` token. Not encrypted — only signed.

    The payload is readable by the holder, which is fine: it carries a username
    they just typed and two timestamps. What matters is that they cannot change
    it, and that a stolen token expires.
    """
    now = int(time.time())
    payload = {
        "sub": username,
        "jti": secrets.token_urlsafe(12),
        "iat": now,
        "exp": now + ttl_seconds,
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{encoded}.{_sign(encoded, secret)}"


def read_session(token: str, *, secret: str, now: int | None = None) -> SessionClaims | None:
    """Validate a token and return its claims, or None for any failure.

    Every rejection collapses to None on purpose. Distinguishing "bad
    signature" from "expired" in the response would tell an attacker which half
    of a forgery attempt worked.
    """
    encoded, separator, signature = token.partition(".")
    if not separator or not encoded or not signature:
        return None
    if not hmac.compare_digest(signature, _sign(encoded, secret)):
        return None

    try:
        payload = json.loads(_b64decode(encoded))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None

    sub, jti = payload.get("sub"), payload.get("jti")
    issued_at, expires_at = payload.get("iat"), payload.get("exp")
    if not isinstance(sub, str) or not isinstance(jti, str):
        return None
    if not isinstance(issued_at, int) or not isinstance(expires_at, int):
        return None
    if (now if now is not None else int(time.time())) >= expires_at:
        return None

    return SessionClaims(sub=sub, jti=jti, issued_at=issued_at, expires_at=expires_at)


# --- configuration -------------------------------------------------------


def auth_configuration_error() -> str | None:
    """Return why auth cannot be enforced, or None when it is ready.

    Called at startup so an unconfigured production container dies on boot
    instead of serving the workbench to anyone who asks.
    """
    if not api_settings.auth_enabled:
        return None
    if not api_settings.auth_username.strip():
        return "AUTH_USERNAME is required when AUTH_ENABLED is true"
    if not api_settings.auth_password_hash.strip():
        return (
            "AUTH_PASSWORD_HASH is required when AUTH_ENABLED is true "
            "(generate one with: python -m dcode_api.hash_password)"
        )
    # Checked for shape, not just presence. A hash that arrives corrupted —
    # the historical case is an env-file interpolation eating it — leaves a
    # non-empty value that rejects every login while the service reports
    # healthy. Refusing to boot is the only honest response to that.
    if _parse_hash(api_settings.auth_password_hash.strip()) is None:
        return (
            "AUTH_PASSWORD_HASH is not a valid hash. Regenerate it with "
            "`python -m dcode_api.hash_password`, and if the value passes "
            "through an env file check that nothing rewrote it"
        )
    if len(api_settings.auth_session_secret.strip()) < 32:
        return "AUTH_SESSION_SECRET must be at least 32 characters when AUTH_ENABLED is true"
    return None


# --- request dependencies ------------------------------------------------


def current_session(
    dcode_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> SessionClaims | None:
    """Read and validate the session cookie. None when absent, invalid, or off."""
    if not api_settings.auth_enabled or not dcode_session:
        return None
    return read_session(dcode_session, secret=api_settings.auth_session_secret)


def require_session(
    session: SessionClaims | None = Depends(current_session),
) -> SessionClaims | None:
    """Router-level gate. A no-op when auth is disabled, 401 otherwise."""
    if not api_settings.auth_enabled:
        return None
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "sign in to use this endpoint"},
        )
    return session


# --- per-session daily query budget --------------------------------------


def quota_key(session: SessionClaims, *, today: str | None = None) -> str:
    """Redis key for one session's spend on one UTC day.

    Keyed by `jti`, so the budget is per sign-in rather than per account —
    which is the only granularity a shared account can offer (D-6).
    """
    day = today or datetime.now(UTC).strftime("%Y-%m-%d")
    return f"authquota:{session.jti}:{day}"


# --- helpers -------------------------------------------------------------


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)
