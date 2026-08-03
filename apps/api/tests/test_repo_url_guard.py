"""Clone-target validation (F-06).

The literal-IP filter these tests sit on top of already existed. What did not
was any check on a *name*, so the interesting cases here are the ones that
would previously have been accepted.
"""

import uuid

import pytest
from dcode_api.deps import get_db, get_index_job_publisher
from dcode_api.main import app
from dcode_api.routes import repos
from fastapi.testclient import TestClient


class _EmptyIndex:
    """A session with no existing repositories, permissive on writes.

    Permissive on purpose: a *rejected* URL must not reach the write path, and a
    test that asserts acceptance needs the write path to succeed. Asserting
    inside the fake conflates the two — it turns "accepted" into a crash, which
    is indistinguishable from a different bug.
    """

    def __init__(self) -> None:
        self.added: list[object] = []

    async def execute(self, _statement: object) -> object:
        class _Result:
            def scalars(self) -> "_Result":
                return self

            def all(self) -> list[object]:
                return []

        return _Result()

    def add(self, row: object) -> None:
        self.added.append(row)
        if getattr(row, "id", None) is None:
            row.id = uuid.uuid4()

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


def _client(session: _EmptyIndex, published: list[str]) -> TestClient:
    async def publish(_repo_id: object, url: str) -> None:
        published.append(url)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_index_job_publisher] = lambda: publish
    return TestClient(app)


def _submit(url: str) -> tuple[int, str]:
    """Submit one URL. Returns (status, rejection message).

    Also asserts the invariant that matters more than either: a rejected URL
    creates no row and queues no job.
    """
    session, published = _EmptyIndex(), []
    client = _client(session, published)
    try:
        response = client.post("/api/v1/repos", json={"url": url})
    finally:
        app.dependency_overrides.clear()

    if response.status_code == 400:
        assert session.added == [], "a rejected URL must not create a repo row"
        assert published == [], "a rejected URL must not be queued for cloning"

    detail = response.json().get("detail", {})
    return response.status_code, str(detail.get("message", "")) if isinstance(detail, dict) else ""


@pytest.mark.parametrize(
    "url",
    [
        "https://user:token@github.com/psf/requests.git",
        "http://someone:hunter2@example.com/x.git",
    ],
)
def test_credentials_in_the_url_are_refused(url: str) -> None:
    """A submitted URL is persisted and echoed back by the status route.

    So a token handed to this endpoint became readable by anyone who could read
    that repository's status. Refused rather than silently stripped — quietly
    rewriting what someone submitted is the worse behaviour.
    """
    code, message = _submit(url)
    assert code == 400
    assert "credentials" in message.lower()


def test_a_hostname_resolving_to_a_private_address_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gap this closes: the old check only ever looked at literal IPs.

    `evil.example.com` pointing at cloud metadata or an internal subnet passed
    every test, because it is a name and names were not resolved.
    """

    async def resolves_to_metadata(_host: str) -> list[str]:
        return ["169.254.169.254"]

    monkeypatch.setattr(repos, "resolve_host", resolves_to_metadata)
    code, message = _submit("https://evil.example.com/x.git")
    assert code == 400
    assert "private or reserved" in message


def test_a_mixed_answer_is_refused_if_any_address_is_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One public answer must not launder a private one."""

    async def mixed(_host: str) -> list[str]:
        return ["140.82.121.4", "10.1.2.3"]

    monkeypatch.setattr(repos, "resolve_host", mixed)
    code, _ = _submit("https://mixed.example.com/x.git")
    assert code == 400


def test_a_resolution_failure_does_not_reject_the_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DNS hiccup is not evidence about the host.

    Rejecting here would report an unrelated network problem as an invalid URL,
    and the clone would fail later with a clearer reason anyway.
    """

    async def unreachable(_host: str) -> list[str]:
        raise OSError("temporary failure in name resolution")

    monkeypatch.setattr(repos, "resolve_host", unreachable)
    code, _ = _submit("https://github.com/psf/requests.git")
    assert code != 400


def test_the_allowlist_is_the_only_positive_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """Everything else filters what is obviously wrong; this states what is right."""
    from dcode_api.settings import api_settings

    monkeypatch.setattr(api_settings, "repo_url_allowed_hosts", "github.com, gitlab.com")

    code, message = _submit("https://bitbucket.org/team/repo.git")
    assert code == 400
    assert "github.com" in message

    assert _submit("https://github.com/psf/requests.git")[0] != 400
    # Subdomains of an allowed host are allowed.
    assert _submit("https://raw.github.com/psf/requests.git")[0] != 400


def test_an_empty_allowlist_permits_any_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from dcode_api.settings import api_settings

    monkeypatch.setattr(api_settings, "repo_url_allowed_hosts", "")
    assert _submit("https://bitbucket.org/team/repo.git")[0] != 400


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://localhost/x.git",
        "https://127.0.0.1/x.git",
        "https://10.0.0.1/x.git",
        "https://[::1]/x.git",
        "not-a-git-url",
    ],
)
def test_previously_covered_rejections_still_hold(url: str) -> None:
    """The literal and scheme filters predate this change and must not regress."""
    assert _submit(url)[0] == 400


def test_an_empty_url_is_refused_by_the_schema_before_the_route() -> None:
    """422, not 400, and that is the right layer.

    `min_length=1` on the request body means an empty URL never reaches the
    validator — the distinction matters only in that a test asserting 400 here
    would be asserting the wrong thing.
    """
    assert _submit("")[0] == 422
