"""POST /repos contract tests — URL validation and idempotency."""

import uuid
from collections.abc import AsyncIterator
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
