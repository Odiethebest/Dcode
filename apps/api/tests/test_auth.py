"""Tests for the single shared-account gate.

The gate is off by default, so most of these turn it on explicitly. That
asymmetry is the point: the default path must be unchanged, and the gated path
must actually refuse.

PBKDF2 runs at a low iteration count here. 600k iterations is right for a login
endpoint and wrong for a test suite that hashes a dozen times.
"""

import time

import httpx
import pytest
from dcode_api.auth import (
    SESSION_COOKIE_NAME,
    auth_configuration_error,
    hash_password,
    issue_session,
    read_session,
    verify_password,
)
from dcode_api.deps import get_agent_client, get_redis
from dcode_api.main import app, create_app
from dcode_api.settings import api_settings
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

_TEST_ITERATIONS = 10
_SECRET = "s" * 48
_PASSWORD = "correct horse battery staple"


@pytest.fixture
def gated(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client with the gate on and a known credential.

    The base URL is https on purpose. The cookie is issued `Secure`, so over
    plain http a client correctly refuses to send it back and every
    post-login assertion would fail for a reason that has nothing to do with
    the gate. Weakening the cookie to make the test pass would delete the
    property being tested — this is also a real operational note: a
    plain-HTTP staging host needs `AUTH_COOKIE_SECURE=false` or logins will
    appear to succeed and never stick.
    """
    monkeypatch.setattr(api_settings, "auth_enabled", True)
    monkeypatch.setattr(api_settings, "auth_username", "reviewer")
    monkeypatch.setattr(
        api_settings,
        "auth_password_hash",
        hash_password(_PASSWORD, iterations=_TEST_ITERATIONS),
    )
    monkeypatch.setattr(api_settings, "auth_session_secret", _SECRET)
    # Set rather than inherited: a test that asserts the cookie is Secure has
    # to establish that, or it passes or fails on the developer's .env.
    monkeypatch.setattr(api_settings, "auth_cookie_secure", True)
    return TestClient(app, base_url="https://testserver")


# --- password hashing ----------------------------------------------------


def test_password_roundtrip() -> None:
    encoded = hash_password(_PASSWORD, iterations=_TEST_ITERATIONS)
    assert verify_password(_PASSWORD, encoded)
    assert not verify_password("wrong", encoded)


def test_password_hash_is_salted() -> None:
    """Two hashes of the same password must differ, or the salt is not doing its job."""
    a = hash_password(_PASSWORD, iterations=_TEST_ITERATIONS)
    b = hash_password(_PASSWORD, iterations=_TEST_ITERATIONS)
    assert a != b
    assert verify_password(_PASSWORD, a) and verify_password(_PASSWORD, b)


@pytest.mark.parametrize("encoded", ["", "not-a-hash", "bcrypt$1$x$y", "pbkdf2_sha256$abc$x$y"])
def test_malformed_hash_denies_rather_than_raises(encoded: str) -> None:
    """A misconfigured hash must deny access, not 500.

    A crash is distinguishable from a wrong password by the caller, which turns
    a configuration mistake into an oracle.
    """
    assert verify_password(_PASSWORD, encoded) is False


# --- session tokens ------------------------------------------------------


def test_session_roundtrip() -> None:
    token = issue_session("reviewer", ttl_seconds=60, secret=_SECRET)
    claims = read_session(token, secret=_SECRET)
    assert claims is not None
    assert claims.sub == "reviewer"
    assert claims.jti


def test_session_rejects_a_tampered_payload() -> None:
    token = issue_session("reviewer", ttl_seconds=60, secret=_SECRET)
    payload, _, signature = token.partition(".")
    forged = f"{payload[:-4]}AAAA.{signature}"
    assert read_session(forged, secret=_SECRET) is None


def test_session_rejects_another_secret() -> None:
    token = issue_session("reviewer", ttl_seconds=60, secret=_SECRET)
    assert read_session(token, secret="d" * 48) is None


def test_session_expires() -> None:
    token = issue_session("reviewer", ttl_seconds=1, secret=_SECRET)
    now = int(time.time())
    assert read_session(token, secret=_SECRET, now=now) is not None
    assert read_session(token, secret=_SECRET, now=now + 2) is None


@pytest.mark.parametrize("token", ["", "nodot", ".", "a.", ".b"])
def test_session_rejects_malformed_tokens(token: str) -> None:
    assert read_session(token, secret=_SECRET) is None


# --- fail closed ---------------------------------------------------------


def test_configuration_error_is_none_when_disabled() -> None:
    assert auth_configuration_error() is None


def test_enabled_without_a_password_hash_is_a_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_settings, "auth_enabled", True)
    monkeypatch.setattr(api_settings, "auth_password_hash", "")
    monkeypatch.setattr(api_settings, "auth_session_secret", _SECRET)
    error = auth_configuration_error()
    assert error is not None and "AUTH_PASSWORD_HASH" in error


def test_a_corrupted_password_hash_is_a_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Presence is not enough — the hash is checked for shape.

    Found live: Docker Compose interpolates `$VAR` inside env-file values, so a
    `$`-separated hash reached the container as 22 characters with three of its
    four segments eaten. Nothing errored. The service reported healthy and
    every login failed forever, with no way to tell that from a wrong password.

    The format now uses "." so the character never appears, and this check is
    the second line: any hash that will not parse stops the boot.
    """
    monkeypatch.setattr(api_settings, "auth_enabled", True)
    monkeypatch.setattr(api_settings, "auth_session_secret", _SECRET)
    for corrupted in ("pbkdf2_sha256", "pbkdf2_sha256.600000", "garbage", "a.b.c.d"):
        monkeypatch.setattr(api_settings, "auth_password_hash", corrupted)
        error = auth_configuration_error()
        assert error is not None, f"{corrupted!r} was accepted as a password hash"
        assert "AUTH_PASSWORD_HASH" in error


def test_password_hash_contains_no_dollar_sign() -> None:
    """The encoded hash must survive an env file unescaped.

    `$` is what Docker Compose expands. A hash carrying one is a credential
    that silently arrives wrong.
    """
    assert "$" not in hash_password(_PASSWORD, iterations=_TEST_ITERATIONS)


def test_enabled_with_a_weak_session_secret_is_a_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_settings, "auth_enabled", True)
    monkeypatch.setattr(api_settings, "auth_password_hash", hash_password("x", iterations=10))
    monkeypatch.setattr(api_settings, "auth_session_secret", "short")
    error = auth_configuration_error()
    assert error is not None and "AUTH_SESSION_SECRET" in error


# --- the gate ------------------------------------------------------------


_PROTECTED = [
    ("post", "/api/v1/repos", {"json": {"url": "https://github.com/psf/requests.git"}}),
    (
        "post",
        "/api/v1/query",
        {"json": {"repo_id": "00000000-0000-0000-0000-000000000000", "query": "hi"}},
    ),
    ("get", "/api/v1/repos/00000000-0000-0000-0000-000000000000/status", {}),
    ("get", "/api/v1/repos/00000000-0000-0000-0000-000000000000/source?file_path=a.py", {}),
    ("get", "/api/v1/repos/00000000-0000-0000-0000-000000000000/neighbors?symbol=x", {}),
]


@pytest.mark.parametrize(("method", "path", "kwargs"), _PROTECTED)
def test_protected_routes_refuse_without_a_session(
    gated: TestClient, method: str, path: str, kwargs: dict[str, object]
) -> None:
    response = getattr(gated, method)(path, **kwargs)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_open_routes_stay_open_with_the_gate_on(gated: TestClient) -> None:
    """Liveness and the session endpoints cannot require a session."""
    assert gated.get("/healthz").status_code == 200
    assert gated.get("/api/v1/auth/me").status_code == 200
    assert gated.post("/api/v1/auth/logout").status_code == 200


def test_me_reports_unauthenticated_before_login(gated: TestClient) -> None:
    body = gated.get("/api/v1/auth/me").json()
    assert body == {"auth_required": True, "authenticated": False, "username": None}


def test_me_reports_no_gate_when_disabled() -> None:
    body = TestClient(app).get("/api/v1/auth/me").json()
    assert body["auth_required"] is False
    assert body["authenticated"] is True


def test_login_rejects_a_wrong_password(gated: TestClient) -> None:
    response = gated.post(
        "/api/v1/auth/login", json={"username": "reviewer", "password": "nope"}
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"
    assert SESSION_COOKIE_NAME not in response.cookies


def test_login_rejects_a_wrong_username(gated: TestClient) -> None:
    response = gated.post(
        "/api/v1/auth/login", json={"username": "someone-else", "password": _PASSWORD}
    )
    assert response.status_code == 401


def test_login_sets_a_hardened_cookie_and_opens_the_gate(gated: TestClient) -> None:
    response = gated.post(
        "/api/v1/auth/login", json={"username": "reviewer", "password": _PASSWORD}
    )
    assert response.status_code == 200
    assert response.json() == {
        "auth_required": True,
        "authenticated": True,
        "username": "reviewer",
    }

    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=lax" in cookie_header

    # The client keeps the cookie, so a previously-401 route now resolves.
    assert gated.get("/api/v1/auth/me").json()["authenticated"] is True
    assert (
        gated.get("/api/v1/repos/00000000-0000-0000-0000-000000000000/status").status_code
        != 401
    )


def test_logout_clears_the_session(gated: TestClient) -> None:
    gated.post("/api/v1/auth/login", json={"username": "reviewer", "password": _PASSWORD})
    assert gated.get("/api/v1/auth/me").json()["authenticated"] is True

    gated.post("/api/v1/auth/logout")
    assert gated.get("/api/v1/auth/me").json()["authenticated"] is False


def test_an_expired_cookie_is_refused(gated: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_settings, "auth_session_ttl_seconds", -1)
    gated.post("/api/v1/auth/login", json={"username": "reviewer", "password": _PASSWORD})
    assert gated.get("/api/v1/auth/me").json()["authenticated"] is False


# --- per-session daily query budget --------------------------------------


class _CountingRedis:
    """Enough Redis for the quota path, and it fails where asked to."""

    def __init__(self, *, fail: bool = False) -> None:
        self.counters: dict[str, int] = {}
        self.expires: list[tuple[str, int]] = []
        self.fail = fail

    async def incr(self, key: str) -> int:
        if self.fail:
            raise RedisError("down")
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.expires.append((key, ttl))

    async def get(self, key: str) -> str | None:
        return None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        return None


def _sign_in(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"username": "reviewer", "password": _PASSWORD}
    )
    assert response.status_code == 200


def _query(client: TestClient) -> int:
    return client.post(
        "/api/v1/query",
        json={"repo_id": "00000000-0000-0000-0000-000000000000", "query": "hi"},
    ).status_code


def test_daily_query_budget_is_enforced_per_session(
    gated: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The login wall stops anonymous callers, not a signed-in loop.

    Counted before the agent is reached, because that is where the metered
    APIs are.
    """
    monkeypatch.setattr(api_settings, "auth_daily_query_limit", 2)
    redis = _CountingRedis()
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_agent_client] = lambda: _NeverCalledAgent()
    try:
        _sign_in(gated)
        assert _query(gated) != 429
        assert _query(gated) != 429
        assert _query(gated) == 429
    finally:
        app.dependency_overrides.clear()

    assert len(redis.counters) == 1, "the budget must be one counter per session per day"
    assert redis.expires and redis.expires[0][1] == 24 * 60 * 60


def test_quota_failure_lets_the_request_through(
    gated: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spend guard is not a security control.

    Refusing every query because Redis is down trades a bounded bill for a
    total outage, which is the worse failure.
    """
    monkeypatch.setattr(api_settings, "auth_daily_query_limit", 1)
    app.dependency_overrides[get_redis] = lambda: _CountingRedis(fail=True)
    app.dependency_overrides[get_agent_client] = lambda: _NeverCalledAgent()
    try:
        _sign_in(gated)
        assert _query(gated) != 429
        assert _query(gated) != 429
    finally:
        app.dependency_overrides.clear()


class _NeverCalledAgent:
    """The quota check runs before the agent, so this only has to exist."""

    def stream(self, method: str, url: str, json: dict[str, object]) -> object:
        raise httpx.ConnectError("agent not part of this test")


# --- docs surface --------------------------------------------------------


def test_docs_are_served_by_default() -> None:
    assert app.openapi_url == "/openapi.json"


def test_docs_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-05: /docs and /openapi.json enumerate the /internal/* surface."""
    monkeypatch.setattr(api_settings, "docs_enabled", False)
    closed = create_app()
    assert closed.openapi_url is None
    assert closed.docs_url is None
    assert closed.redoc_url is None
    assert TestClient(closed).get("/openapi.json").status_code == 404
