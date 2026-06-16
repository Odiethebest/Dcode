"""API gateway smoke tests: health + indexing API contracts."""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from dcode_api.deps import get_db, get_index_job_publisher, get_redis
from dcode_api.main import app
from dcode_shared.cache import job_state_key
from dcode_shared.db.models import Repo
from fastapi.testclient import TestClient


class FakeSession:
    def __init__(self, repo: Repo | None = None) -> None:
        self.repo = repo
        self.committed = False
        self.rolled_back = False

    def add(self, repo: Repo) -> None:
        self.repo = repo

    async def flush(self) -> None:
        if self.repo is not None and self.repo.id is None:
            self.repo.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def get(self, _: type[Repo], repo_id: uuid.UUID) -> Repo | None:
        if self.repo is not None and self.repo.id == repo_id:
            return self.repo
        return None


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


class FakePublisher:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[uuid.UUID, str]] = []

    async def __call__(self, repo_id: uuid.UUID, repo_url: str) -> None:
        if self.fail:
            raise RuntimeError("queue unavailable")
        self.calls.append((repo_id, repo_url))


def override_dependencies(
    session: FakeSession,
    publisher: FakePublisher | None = None,
    redis: FakeRedis | None = None,
) -> None:
    async def override_db() -> AsyncIterator[FakeSession]:
        yield session

    async def override_publisher() -> FakePublisher:
        return publisher or FakePublisher()

    async def override_redis() -> FakeRedis:
        return redis or FakeRedis()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_index_job_publisher] = override_publisher
    app.dependency_overrides[get_redis] = override_redis


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_healthz_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_submit_repo_returns_202_with_correct_shape() -> None:
    """DESIGN.md §4.1 POST /api/v1/repos must return 202 + RepoCreateResponse."""
    session = FakeSession()
    publisher = FakePublisher()
    override_dependencies(session, publisher)

    client = TestClient(app)
    response = client.post(
        "/api/v1/repos",
        json={"url": "https://github.com/psf/requests.git"},
    )
    assert response.status_code == 202
    body = response.json()
    assert "repo_id" in body
    assert body["status"] == "queued"
    assert session.repo is not None
    assert session.repo.url == "https://github.com/psf/requests.git"
    assert session.committed is True
    assert publisher.calls == [(uuid.UUID(body["repo_id"]), "https://github.com/psf/requests.git")]


def test_submit_repo_rejects_malformed_url() -> None:
    """Malformed repo URLs fail before queue publication."""
    session = FakeSession()
    publisher = FakePublisher()
    override_dependencies(session, publisher)

    client = TestClient(app)
    response = client.post("/api/v1/repos", json={"url": "not a url"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_REPO_URL"
    assert session.repo is None
    assert publisher.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/example/repo.git",
        "https://127.0.0.1/repo.git",
        "ssh://10.0.0.8/repo.git",
        "git://[::1]/repo.git",
        "git@localhost:team/repo.git",
    ],
)
def test_submit_repo_rejects_local_or_private_git_urls(url: str) -> None:
    session = FakeSession()
    publisher = FakePublisher()
    override_dependencies(session, publisher)

    response = TestClient(app).post("/api/v1/repos", json={"url": url})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_REPO_URL"
    assert publisher.calls == []


def test_submit_repo_rolls_back_when_publish_fails() -> None:
    session = FakeSession()
    publisher = FakePublisher(fail=True)
    override_dependencies(session, publisher)

    client = TestClient(app)
    response = client.post(
        "/api/v1/repos",
        json={"url": "https://github.com/psf/requests.git"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "INDEX_QUEUE_UNAVAILABLE"
    assert session.committed is False
    assert session.rolled_back is True


def test_repo_status_returns_correct_shape() -> None:
    """DESIGN.md §4.1 GET /api/v1/repos/{id}/status must return RepoStatusResponse."""
    rid = uuid.uuid4()
    repo = Repo(id=rid, url="https://github.com/psf/requests.git", status="embedding", progress=40)
    live_state = {
        "status": "embedding",
        "progress": 47,
        "stages": {
            "cloning": "done",
            "parsing": "done",
            "embedding": "in_progress",
            "graphing": "pending",
        },
    }
    session = FakeSession(repo)
    redis = FakeRedis({job_state_key(str(rid)): json.dumps(live_state)})
    override_dependencies(session, redis=redis)

    client = TestClient(app)
    response = client.get(f"/api/v1/repos/{rid}/status")
    assert response.status_code == 200
    body = response.json()
    assert body["repo_id"] == str(rid)
    assert body["status"] == "embedding"
    assert body["progress"] == 47
    assert set(body["stages"]) == {"cloning", "parsing", "embedding", "graphing"}
    assert body["stages"]["cloning"] == "done"
    assert body["stages"]["embedding"] == "in_progress"


def test_repo_status_404_for_unknown_repo() -> None:
    override_dependencies(FakeSession())

    client = TestClient(app)
    response = client.get(f"/api/v1/repos/{uuid.uuid4()}/status")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "REPO_NOT_FOUND"
