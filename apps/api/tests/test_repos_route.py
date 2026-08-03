"""POST /repos contract tests — URL validation and idempotency."""

import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from dcode_api.deps import get_db, get_index_job_publisher
from dcode_api.main import app
from dcode_shared.db.models import Repo
from fastapi.testclient import TestClient


class FakeResult:
    def __init__(self, repos: list[Repo]) -> None:
        self._repos = repos

    def scalars(self) -> "FakeResult":
        return self

    def all(self) -> list[Repo]:
        return self._repos


class FakeSession:
    """Session stub that replays a fixed candidate set for the reuse lookup.

    The route's filtering (URL variants, reusable statuses) is exercised through
    `matching`, which mimics what the SQL WHERE clauses would have selected.
    """

    def __init__(self, repos: list[Repo] | None = None) -> None:
        self.repos = repos or []
        self.added: list[Repo] = []
        self.commits = 0

    async def execute(self, statement: object) -> FakeResult:
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]
        wanted = {
            repo
            for repo in self.repos
            if f"'{repo.url}'" in compiled and f"'{repo.status}'" in compiled
        }
        return FakeResult(sorted(wanted, key=lambda r: r.created_at, reverse=True))

    def add(self, repo: Repo) -> None:
        self.added.append(repo)
        if repo.id is None:
            repo.id = uuid.uuid4()

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def override(session: FakeSession, published: list[tuple[UUID, str]]) -> None:
    async def db_dependency() -> AsyncIterator[FakeSession]:
        yield session

    async def publisher_dependency() -> Any:
        async def publish(repo_id: UUID, url: str) -> None:
            published.append((repo_id, url))

        return publish

    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[get_index_job_publisher] = publisher_dependency


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _repo(url: str, status: str, age_minutes: int = 0) -> Repo:
    return Repo(
        id=uuid.uuid4(),
        url=url,
        status=status,
        progress=100 if status == "ready" else 0,
        created_at=datetime(2026, 7, 29, 12, 0) - timedelta(minutes=age_minutes),
    )


def test_submit_creates_and_queues_a_new_repo() -> None:
    session = FakeSession()
    published: list[tuple[UUID, str]] = []
    override(session, published)

    response = TestClient(app).post(
        "/api/v1/repos", json={"url": "https://github.com/psf/requests.git"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["reused"] is False
    assert len(published) == 1


def test_resubmitting_a_ready_repo_reuses_it_instead_of_recloning() -> None:
    """The demo-day bug: clicking Index twice used to duplicate the whole repo."""
    existing = _repo("https://github.com/psf/requests.git", "ready")
    session = FakeSession([existing])
    published: list[tuple[UUID, str]] = []
    override(session, published)

    response = TestClient(app).post(
        "/api/v1/repos", json={"url": "https://github.com/psf/requests.git"}
    )

    assert response.status_code == 200  # nothing was accepted for processing
    body = response.json()
    assert body["repo_id"] == str(existing.id)
    assert body["status"] == "ready"
    assert body["reused"] is True
    assert published == []  # no second clone queued
    assert session.added == []  # no second row


@pytest.mark.parametrize(
    "resubmitted",
    [
        "https://github.com/psf/requests",  # no .git
        "https://github.com/psf/requests.git/",  # trailing slash
        "https://GitHub.com/psf/requests.git",  # host case
    ],
)
def test_reuse_matches_equivalent_spellings_of_the_same_url(resubmitted: str) -> None:
    existing = _repo("https://github.com/psf/requests.git", "ready")
    session = FakeSession([existing])
    published: list[tuple[UUID, str]] = []
    override(session, published)

    response = TestClient(app).post("/api/v1/repos", json={"url": resubmitted})

    assert response.json()["reused"] is True
    assert published == []


def test_resubmitting_while_still_indexing_joins_the_running_job() -> None:
    existing = _repo("https://github.com/psf/requests.git", "embedding")
    session = FakeSession([existing])
    published: list[tuple[UUID, str]] = []
    override(session, published)

    body = TestClient(app).post(
        "/api/v1/repos", json={"url": "https://github.com/psf/requests.git"}
    ).json()

    assert body["repo_id"] == str(existing.id)
    assert body["status"] == "embedding"
    assert body["reused"] is True
    assert published == []


def test_a_failed_repo_is_not_reused_so_retry_still_works() -> None:
    failed = _repo("https://github.com/psf/requests.git", "failed")
    session = FakeSession([failed])
    published: list[tuple[UUID, str]] = []
    override(session, published)

    response = TestClient(app).post(
        "/api/v1/repos", json={"url": "https://github.com/psf/requests.git"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["reused"] is False
    assert body["repo_id"] != str(failed.id)
    assert len(published) == 1


def test_ready_wins_over_an_in_progress_duplicate() -> None:
    ready = _repo("https://github.com/psf/requests.git", "ready", age_minutes=30)
    indexing = _repo("https://github.com/psf/requests.git", "cloning", age_minutes=1)
    session = FakeSession([indexing, ready])
    override(session, [])

    body = TestClient(app).post(
        "/api/v1/repos", json={"url": "https://github.com/psf/requests.git"}
    ).json()

    # Newer, but not usable yet — the indexed one is the useful answer.
    assert body["repo_id"] == str(ready.id)


def test_a_different_repo_is_not_collapsed_into_an_existing_one() -> None:
    existing = _repo("https://github.com/psf/requests.git", "ready")
    session = FakeSession([existing])
    published: list[tuple[UUID, str]] = []
    override(session, published)

    body = TestClient(app).post(
        "/api/v1/repos", json={"url": "https://github.com/encode/httpx.git"}
    ).json()

    assert body["reused"] is False
    assert len(published) == 1


def test_rejects_a_non_git_url() -> None:
    session = FakeSession()
    override(session, [])

    response = TestClient(app).post("/api/v1/repos", json={"url": "http://localhost/evil"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_REPO_URL"


class _FakeScalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _ListOnlyDb:
    """Answers the one SELECT the list route makes, with a fixed page.

    The route applies `.limit(_REPO_LIST_LIMIT + 1)` itself, so the fake honours
    it rather than handing back everything — otherwise the truncation test would
    be asserting against a query that never ran.
    """

    def __init__(self, rows: list[object]) -> None:
        from dcode_api.routes.repos import _REPO_LIST_LIMIT

        self._rows = rows[: _REPO_LIST_LIMIT + 1]

    async def execute(self, _statement: object) -> _FakeResult:
        return _FakeResult(self._rows)


def _repo_row(repo_id: str, url: str, status: str) -> object:
    from types import SimpleNamespace
    from uuid import UUID

    return SimpleNamespace(id=UUID(repo_id), url=url, status=status)


@contextmanager
def _repo_list_client(rows: list[object]) -> Iterator[TestClient]:
    from dcode_api.deps import get_db
    from dcode_api.main import app

    app.dependency_overrides[get_db] = lambda: _ListOnlyDb(rows)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- GET /api/v1/repos (F-09) --------------------------------------------


def test_repo_list_returns_newest_first_and_reports_no_truncation() -> None:
    """The endpoint that stops a fresh browser opening an empty workbench."""
    from dcode_shared.schemas import RepoListResponse

    rows = [
        _repo_row("11111111-1111-1111-1111-111111111111", "https://github.com/a/one.git", "ready"),
        _repo_row("22222222-2222-2222-2222-222222222222", "https://github.com/b/two.git", "queued"),
    ]
    with _repo_list_client(rows) as client:
        body = RepoListResponse.model_validate(client.get("/api/v1/repos").json())

    assert [str(repo.repo_id) for repo in body.repos] == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    assert body.truncated is False


def test_repo_list_caps_the_page_and_says_so() -> None:
    """Truncation is reported, not inferred from a full page.

    A caller cannot tell a page that happens to be full from one that was cut,
    and quietly showing a subset is the kind of unstated claim this project
    avoids everywhere else.
    """
    from dcode_api.routes.repos import _REPO_LIST_LIMIT
    from dcode_shared.schemas import RepoListResponse

    rows = [
        _repo_row(f"{index:08d}-0000-0000-0000-000000000000", f"https://x/{index}.git", "ready")
        for index in range(_REPO_LIST_LIMIT + 5)
    ]
    with _repo_list_client(rows) as client:
        body = RepoListResponse.model_validate(client.get("/api/v1/repos").json())

    assert len(body.repos) == _REPO_LIST_LIMIT
    assert body.truncated is True


def test_repo_list_does_not_offer_a_row_whose_status_is_unreadable() -> None:
    """An unrecognised status becomes `failed`, not `ready`.

    Offering a repository as selectable when this code cannot tell what state
    it is in would put a reader in a workbench that answers nothing.
    """
    from dcode_shared.schemas import RepoListResponse

    rows = [_repo_row("33333333-3333-3333-3333-333333333333", "https://x/y.git", "who-knows")]
    with _repo_list_client(rows) as client:
        body = RepoListResponse.model_validate(client.get("/api/v1/repos").json())

    assert body.repos[0].status == "failed"
