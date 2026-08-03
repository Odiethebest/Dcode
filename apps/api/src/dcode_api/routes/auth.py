"""Session endpoints for the shared-account gate.

These three routes are deliberately **not** behind the gate — a login endpoint
that requires a login is a locked door with the key inside. Everything else
under /api/v1 is protected in main.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from dcode_api.auth import (
    SESSION_COOKIE_NAME,
    SessionClaims,
    current_session,
    issue_session,
    verify_password,
)
from dcode_api.settings import api_settings

router = APIRouter(tags=["auth"], prefix="/auth")


class LoginRequest(BaseModel):
    """Credentials for the single shared account."""

    username: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=1, max_length=400)


class SessionState(BaseModel):
    """What the SPA needs to decide whether to show a gate.

    `auth_required` is separate from `authenticated` so the frontend behaves
    correctly in both deployments: with the gate off it must not redirect to a
    login page that would accept anything.
    """

    auth_required: bool
    authenticated: bool
    username: str | None = None


@router.post("/login", response_model=SessionState)
async def login(body: LoginRequest, response: Response) -> SessionState:
    """Exchange credentials for a signed session cookie."""
    if not api_settings.auth_enabled:
        # Nothing to sign in to. Report the state rather than minting a cookie
        # that would imply a gate exists.
        return SessionState(auth_required=False, authenticated=True, username=None)

    username_ok = body.username.strip() == api_settings.auth_username.strip()
    password_ok = verify_password(body.password, api_settings.auth_password_hash)
    # Both checks always run. Returning early on an unknown username would let
    # the response time distinguish "wrong user" from "wrong password".
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "incorrect username or password"},
        )

    token = issue_session(
        api_settings.auth_username.strip(),
        ttl_seconds=api_settings.auth_session_ttl_seconds,
        secret=api_settings.auth_session_secret,
    )
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=api_settings.auth_session_ttl_seconds,
        httponly=True,
        secure=api_settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return SessionState(
        auth_required=True, authenticated=True, username=api_settings.auth_username.strip()
    )


@router.post("/logout", response_model=SessionState)
async def logout(response: Response) -> SessionState:
    """Clear the session cookie.

    The token stays valid until it expires — there is no server-side session
    store to revoke it in, which is the cost of D-6 and is recorded there.
    """
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return SessionState(
        auth_required=api_settings.auth_enabled, authenticated=not api_settings.auth_enabled
    )


@router.get("/me", response_model=SessionState)
async def me(session: SessionClaims | None = Depends(current_session)) -> SessionState:
    """Report session state. Always 200 — the SPA decides what to do with it.

    A 401 here would be indistinguishable from a network failure at the point
    where the frontend is deciding whether to render a gate at all.
    """
    if not api_settings.auth_enabled:
        return SessionState(auth_required=False, authenticated=True, username=None)
    return SessionState(
        auth_required=True,
        authenticated=session is not None,
        username=session.sub if session else None,
    )
